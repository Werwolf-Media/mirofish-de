"""
图谱相关API路由
采用项目上下文机制，服务端持久化状态
"""

import os
import traceback
import threading
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..services.german_sources import GermanSourcesService
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# 获取日志器
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== 项目管理接口 ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    获取项目详情
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    列出所有项目
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)
    
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    删除项目
    """
    success = ProjectManager.delete_project(project_id)
    
    if not success:
        return jsonify({
            "success": False,
            "error": t('api.projectDeleteFailed', id=project_id)
        }), 404

    return jsonify({
        "success": True,
        "message": t('api.projectDeleted', id=project_id)
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    重置项目状态（用于重新构建图谱）
    """
    project = ProjectManager.get_project(project_id)
    
    if not project:
        return jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404

    # 重置到本体已生成状态
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED
    
    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)
    
    return jsonify({
        "success": True,
        "message": t('api.projectReset', id=project_id),
        "data": project.to_dict()
    })


# ============== 接口1：上传文件并生成本体 ==============

class OntologyInputError(ValueError):
    """400er-Fall: fehlendes oder unbrauchbares Seed-Material."""


class OntologyPipelineFailure(Exception):
    """Pipeline nach Projekt-Anlage gescheitert — traegt das Projekt fuer das Fehler-Handling."""

    def __init__(self, project, cause):
        super().__init__(str(cause))
        self.project = project
        self.cause = cause


def run_ontology_pipeline(project_name, simulation_requirement, additional_context='',
                          include_german_sources=False, seed_text='',
                          incoming_files=None, disk_files=None, billing_name=None):
    """
    Kern von Schritt 1 (Ontologie-Generierung): Projekt anlegen, Seed-Material
    einlesen, Ontologie generieren. Genutzt von /api/graph/ontology/generate
    (Browser-Upload) UND /api/groups/<id>/run (serverseitiger Projekt-Seed).

    incoming_files: Liste von FileStorage (Upload)
    disk_files:     Liste von (original_name, dateipfad) — bereits auf Platte
    Rueckgabe: data-Dict (wie im API-Response); wirft OntologyInputError (400)
    oder OntologyPipelineFailure (Projekt existiert, Schritt gescheitert).
    """
    project = ProjectManager.create_project(name=project_name)
    try:
        project.simulation_requirement = simulation_requirement
        logger.info(f"创建项目: {project.project_id}")

        # Abrechnung: Run-Start markieren + OpenRouter-Verbrauch snapshoten (vor jedem LLM-Aufruf)
        try:
            from ..models.billing import BillingManager
            from ..utils.openrouter_cost import get_usage as _or_usage
            BillingManager.start(project.project_id, billing_name or project_name,
                                 simulation_requirement, _or_usage())
        except Exception as _e:
            logger.warning(f"Abrechnung Start-Hook fehlgeschlagen: {_e}")

        # Seed-Material einlesen und Text extrahieren
        document_texts = []
        all_text = ""

        def _ingest(file_info):
            nonlocal all_text
            project.files.append({
                "filename": file_info["original_filename"],
                "size": file_info["size"]
            })
            text = FileParser.extract_text(file_info["path"])
            text = TextProcessor.preprocess_text(text)
            document_texts.append(text)
            all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"

        for file in (incoming_files or []):
            if file and file.filename and allowed_file(file.filename):
                _ingest(ProjectManager.save_file_to_project(
                    project.project_id, file, file.filename
                ))

        for original_name, src_path in (disk_files or []):
            if allowed_file(original_name) and os.path.isfile(src_path):
                _ingest(ProjectManager.copy_file_to_project(
                    project.project_id, src_path, original_name
                ))

        # Seed-Text (z. B. strukturierte Beschreibung aus dem Onboarding-Assistenten)
        if seed_text:
            processed_seed = TextProcessor.preprocess_text(seed_text)
            document_texts.append(processed_seed)
            all_text += f"\n\n=== {t('api.seedTextLabel')} ===\n{processed_seed}"
            project.files.append({
                "filename": t('api.seedTextLabel'),
                "size": len(processed_seed)
            })

        # Opt-in: aktuelle deutsche Quellen als zusaetzliches Seed-Material einbinden
        german_sources_count = 0
        if include_german_sources:
            logger.info(t('api.germanSourcesFetching'))
            try:
                source_text, source_items = GermanSourcesService.fetch(simulation_requirement)
                if source_text:
                    processed = TextProcessor.preprocess_text(source_text)
                    document_texts.append(processed)
                    all_text += f"\n\n=== {t('api.germanSourcesHeader')} ===\n{processed}"
                    german_sources_count = len(source_items)
                    project.files.append({
                        "filename": t('api.germanSourcesFilename'),
                        "size": len(processed)
                    })
                    logger.info(t('api.germanSourcesAdded', count=german_sources_count))
                else:
                    logger.info(t('api.germanSourcesNone'))
            except Exception as e:
                logger.warning(t('api.germanSourcesFailed', error=str(e)))

        if not document_texts:
            ProjectManager.delete_project(project.project_id)
            raise OntologyInputError(t('api.noDocProcessed'))

        # Extrahierten Text speichern
        project.total_text_length = len(all_text)
        ProjectManager.save_extracted_text(project.project_id, all_text)
        logger.info(f"文本提取完成，共 {len(all_text)} 字符")

        # Ontologie generieren
        logger.info("调用 LLM 生成本体定义...")
        generator = OntologyGenerator()
        ontology = generator.generate(
            document_texts=document_texts,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context if additional_context else None
        )

        entity_count = len(ontology.get("entity_types", []))
        edge_count = len(ontology.get("edge_types", []))
        logger.info(f"本体生成完成: {entity_count} 个实体类型, {edge_count} 个关系类型")

        project.ontology = {
            "entity_types": ontology.get("entity_types", []),
            "edge_types": ontology.get("edge_types", [])
        }
        project.analysis_summary = ontology.get("analysis_summary", "")
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)
        logger.info(f"=== 本体生成完成 === 项目ID: {project.project_id}")

        return {
            "project_id": project.project_id,
            "project_name": project.name,
            "ontology": project.ontology,
            "analysis_summary": project.analysis_summary,
            "files": project.files,
            "total_text_length": project.total_text_length,
            "german_sources_count": german_sources_count
        }
    except OntologyInputError:
        raise
    except Exception as e:
        raise OntologyPipelineFailure(project, e)


def ontology_error_response(error, project):
    """
    Upstream-Fix portiert: Klartext-Fehler statt rohem Traceback ans Frontend;
    Provider-Bodies koennen Request-Inhalte echoen und werden nicht serialisiert.
    Gemeinsames Fehler-Handling fuer /ontology/generate und /api/groups/<id>/run.
    """
    provider_status = getattr(error, "status_code", None)
    request_id = getattr(error, "request_id", None)

    from ..utils.llm_client import LLMResponseError
    if isinstance(error, LLMResponseError):
        public_error = str(error)
        response_status = 502
        logger.exception("LLM returned an unusable ontology response")
    elif isinstance(provider_status, int):
        public_error = f"LLM provider request failed (HTTP {provider_status})"
        if request_id:
            import re as _re
            safe_request_id = _re.sub(
                r"[^a-zA-Z0-9._:-]", "", str(request_id)
            )[:128]
            if safe_request_id:
                public_error += f" (request_id: {safe_request_id})"
        response_status = 502
        logger.error(
            "Ontology provider request failed: type=%s status=%s request_id=%s",
            type(error).__name__,
            provider_status,
            request_id or "unknown",
        )
    else:
        public_error = str(error) or "Ontology generation failed"
        response_status = 500
        logger.exception("Unexpected ontology generation failure")

    response_data = None
    if project is not None:
        project.status = ProjectStatus.FAILED
        try:
            ProjectManager.save_project(project)
        except Exception:
            logger.exception(
                "Failed to persist ontology failure for project %s",
                project.project_id,
            )
        response_data = {"project_id": project.project_id}

    payload = {
        "success": False,
        "error": public_error,
    }
    if response_data is not None:
        payload["data"] = response_data
    return jsonify(payload), response_status


@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    接口1：上传文件，分析生成本体定义（multipart/form-data）

    参数: files (PDF/MD/TXT, mehrere) · simulation_requirement (Pflicht)
          · project_name · additional_context · seed_text · include_german_sources
    """
    try:
        logger.info("=== 开始生成本体定义 ===")

        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')
        include_german_sources = request.form.get('include_german_sources', '') \
            .strip().lower() in ('1', 'true', 'yes', 'on')
        seed_text = request.form.get('seed_text', '').strip()

        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationRequirement')
            }), 400

        uploaded_files = request.files.getlist('files')
        has_files = bool(uploaded_files) and any(f.filename for f in uploaded_files)
        # Seed-Material kann aus Dateien, einem seed_text oder den deutschen Quellen stammen
        if not has_files and not seed_text and not include_german_sources:
            return jsonify({
                "success": False,
                "error": t('api.requireFileUpload')
            }), 400

        data = run_ontology_pipeline(
            project_name=project_name,
            simulation_requirement=simulation_requirement,
            additional_context=additional_context,
            include_german_sources=include_german_sources,
            seed_text=seed_text,
            incoming_files=uploaded_files,
        )
        return jsonify({"success": True, "data": data})

    except OntologyInputError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except OntologyPipelineFailure as pf:
        return ontology_error_response(pf.cause, pf.project)
    except Exception as error:
        return ontology_error_response(error, None)


# ============== 接口2：构建图谱 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    接口2：根据project_id构建图谱
    
    请求（JSON）：
        {
            "project_id": "proj_xxxx",  // 必填，来自接口1
            "graph_name": "图谱名称",    // 可选
            "chunk_size": 500,          // 可选，默认500
            "chunk_overlap": 50         // 可选，默认50
        }
        
    返回：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "图谱构建任务已启动"
            }
        }
    """
    try:
        logger.info("=== 开始构建图谱 ===")
        
        # 检查配置
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append(t('api.zepApiKeyMissing'))
        if errors:
            logger.error(f"配置错误: {errors}")
            return jsonify({
                "success": False,
                "error": t('api.configError', details="; ".join(errors))
            }), 500
        
        # 解析请求
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"请求参数: project_id={project_id}")
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": t('api.requireProjectId')
            }), 400
        
        # 获取项目
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=project_id)
            }), 404

        # 检查项目状态
        force = data.get('force', False)  # 强制重新构建
        
        if project.status == ProjectStatus.CREATED:
            return jsonify({
                "success": False,
                "error": t('api.ontologyNotGenerated')
            }), 400
        
        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": t('api.graphBuilding'),
                "task_id": project.graph_build_task_id
            }), 400
        
        # 如果强制重建，重置状态
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None
        
        # 获取配置
        graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)
        
        # 更新项目配置
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap
        
        # 获取提取的文本
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": t('api.textNotFound')
            }), 400
        
        # 获取本体
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": t('api.ontologyNotFound')
            }), 400
        
        # 创建异步任务
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"构建图谱: {graph_name}")
        logger.info(f"创建图谱构建任务: task_id={task_id}, project_id={project_id}")
        
        # 更新项目状态
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)
        
        # Capture locale before spawning background thread
        current_locale = get_locale()

        # 启动后台任务
        def build_task():
            set_locale(current_locale)
            build_logger = get_logger('mirofish.build')
            try:
                build_logger.info(f"[{task_id}] 开始构建图谱...")
                task_manager.update_task(
                    task_id, 
                    status=TaskStatus.PROCESSING,
                    message=t('progress.initGraphService')
                )
                
                # 创建图谱构建服务
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
                
                # 分块
                task_manager.update_task(
                    task_id,
                    message=t('progress.textChunking'),
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text, 
                    chunk_size=chunk_size, 
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)
                
                # 创建图谱
                task_manager.update_task(
                    task_id,
                    message=t('progress.creatingZepGraph'),
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)
                
                # 更新项目的graph_id
                project.graph_id = graph_id
                ProjectManager.save_project(project)
                
                # 设置本体
                task_manager.update_task(
                    task_id,
                    message=t('progress.settingOntology'),
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)
                
                # 添加文本（progress_callback 签名是 (msg, progress_ratio)）
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                task_manager.update_task(
                    task_id,
                    message=t('progress.addingChunks', count=total_chunks),
                    progress=15
                )
                
                episode_uuids = builder.add_text_batches(
                    graph_id, 
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )
                
                # 等待Zep处理完成（查询每个episode的processed状态）
                task_manager.update_task(
                    task_id,
                    message=t('progress.waitingZepProcess'),
                    progress=55
                )
                
                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )
                
                builder._wait_for_episodes(episode_uuids, wait_progress_callback)
                
                # 获取图谱数据
                task_manager.update_task(
                    task_id,
                    message=t('progress.fetchingGraphData'),
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)
                
                # 更新项目状态
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)
                
                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] 图谱构建完成: graph_id={graph_id}, 节点={node_count}, 边={edge_count}")
                
                # 完成
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message=t('progress.graphBuildComplete'),
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )
                
            except Exception as e:
                # 更新项目状态为失败
                build_logger.error(f"[{task_id}] 图谱构建失败: {str(e)}")
                build_logger.debug(traceback.format_exc())
                
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=t('progress.buildFailed', error=str(e)),
                    error=traceback.format_exc()
                )
        
        # 启动后台线程
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": t('api.graphBuildStarted', taskId=task_id)
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 任务查询接口 ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    查询任务状态
    """
    task = TaskManager().get_task(task_id)
    
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    
    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有任务
    """
    tasks = TaskManager().list_tasks()
    
    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== 图谱数据接口 ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    获取图谱数据（节点和边）
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(graph_id)
        
        return jsonify({
            "success": True,
            "data": graph_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    删除Zep图谱
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": t('api.zepApiKeyMissing')
            }), 500
        
        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)
        
        return jsonify({
            "success": True,
            "message": t('api.graphDeleted', id=graph_id)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
