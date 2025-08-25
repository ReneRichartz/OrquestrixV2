from flask import Blueprint, abort, send_file, Response
from io import BytesIO
from ..models import File
from ..services.openai_client import get_openai_client

bp = Blueprint('files', __name__)


@bp.get('/<int:file_id>/download')
def download(file_id: int):
    f = File.query.get_or_404(file_id)
    if not f.openai_file_id:
        abort(404)
    client = get_openai_client()
    # Holen der Bytes vom OpenAI File Storage
    data = client.retrieve_file_content(f.openai_file_id)
    bio = BytesIO(data)
    # Inline Text / ansonsten generic octet-stream
    return send_file(bio, as_attachment=True, download_name=f.filename or 'file', mimetype='application/octet-stream')
