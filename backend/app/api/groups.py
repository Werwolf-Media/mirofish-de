"""
Projektmappen-API ("Projekte" im UI).

Ein Projekt = fester Realitäts-Seed (Dokumente + optionaler Seed-Text),
darauf beliebig viele Runs mit unterschiedlichen Prompts. Ein Run erzeugt
über die gemeinsame Ontologie-Pipeline ein normales MiroFish-Projekt und
läuft danach durch die unveränderte Schritt-Kette (Graph → Simulation →
Bericht).

Alle Routen liegen hinter dem App-Token (keine Gate-Ausnahme).
"""

from flask import request, jsonify

from . import groups_bp
from ..models.project_group import ProjectGroupManager
from ..utils.logger import get_logger
from ..utils.locale import t
from .graph import (
    allowed_file,
    run_ontology_pipeline,
    ontology_error_response,
    OntologyInputError,
    OntologyPipelineFailure,
)

logger = get_logger('mirofish.api.groups')


@groups_bp.route('/create', methods=['POST'])
def create_group():
    """
    Projektmappe anlegen (multipart/form-data):
        name: Projektname (Pflicht)
        seed_text: optionaler Seed-Text
        files: Seed-Dokumente (PDF/MD/TXT), mehrere möglich
    """
    name = (request.form.get('name') or '').strip()
    seed_text = (request.form.get('seed_text') or '').strip()
    uploaded = [f for f in request.files.getlist('files') if f and f.filename]

    if not name:
        return jsonify({"success": False, "error": t('groups.nameRequired')}), 400
    if not uploaded and not seed_text:
        return jsonify({"success": False, "error": t('groups.seedRequired')}), 400

    group = ProjectGroupManager.create(name=name, seed_text=seed_text)

    skipped = []
    for f in uploaded:
        if allowed_file(f.filename):
            ProjectGroupManager.save_file(group['group_id'], f, f.filename)
        else:
            skipped.append(f.filename)

    group = ProjectGroupManager.get(group['group_id'])
    if not group['files'] and not seed_text:
        # Alle Dateien unbrauchbar -> aufräumen
        ProjectGroupManager.delete(group['group_id'])
        return jsonify({"success": False, "error": t('groups.seedRequired')}), 400

    logger.info(f"Projektmappe angelegt: {group['group_id']} ({name}), "
                f"{len(group['files'])} Datei(en)")
    return jsonify({"success": True, "data": group, "skipped_files": skipped})


@groups_bp.route('/list', methods=['GET'])
def list_groups():
    return jsonify({"success": True, "data": ProjectGroupManager.list()})


@groups_bp.route('/<group_id>', methods=['GET'])
def get_group(group_id: str):
    group = ProjectGroupManager.get(group_id)
    if not group:
        return jsonify({"success": False, "error": t('groups.notFound')}), 404
    return jsonify({"success": True, "data": group})


@groups_bp.route('/<group_id>', methods=['DELETE'])
def delete_group(group_id: str):
    """Löscht nur die Mappe (Seed + Run-Zuordnung) — die einzelnen
    MiroFish-Projekte/Berichte der Runs bleiben im Verlauf erhalten."""
    if not ProjectGroupManager.delete(group_id):
        return jsonify({"success": False, "error": t('groups.notFound')}), 404
    return jsonify({"success": True})


@groups_bp.route('/<group_id>/run', methods=['POST'])
def run_in_group(group_id: str):
    """
    Neuen Run in einer Projektmappe starten (JSON):
        simulation_requirement: der Prompt dieses Runs (Pflicht)
        additional_context: optional
        include_german_sources: optional (zusätzlich zum Projekt-Seed)

    Antwortformat identisch zu /api/graph/ontology/generate — das Frontend
    fährt danach die normale Schritt-Kette (Graph-Build usw.).
    """
    group = ProjectGroupManager.get(group_id)
    if not group:
        return jsonify({"success": False, "error": t('groups.notFound')}), 404

    data = request.get_json(silent=True) or {}
    requirement = (data.get('simulation_requirement') or '').strip()
    if not requirement:
        return jsonify({
            "success": False,
            "error": t('api.requireSimulationRequirement')
        }), 400

    run_no = len(group.get('runs', [])) + 1
    project_name = f"{group['name']} – Run {run_no}"

    try:
        result = run_ontology_pipeline(
            project_name=project_name,
            simulation_requirement=requirement,
            additional_context=(data.get('additional_context') or '').strip(),
            include_german_sources=bool(data.get('include_german_sources')),
            seed_text=group.get('seed_text', ''),
            disk_files=ProjectGroupManager.disk_files(group_id),
            billing_name=project_name,
        )
    except OntologyInputError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except OntologyPipelineFailure as pf:
        return ontology_error_response(pf.cause, pf.project)
    except Exception as error:
        return ontology_error_response(error, None)

    ProjectGroupManager.add_run(group_id, result['project_id'], requirement)
    logger.info(f"Projektmappe {group_id}: Run {run_no} gestartet "
                f"-> {result['project_id']}")
    result['group_id'] = group_id
    return jsonify({"success": True, "data": result})
