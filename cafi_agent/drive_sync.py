import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
logger = logging.getLogger(__name__)

def get_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                logger.error("No se encontró credentials.json. Saltando sincronización de Drive.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def _get_or_create_folder(service, folder_name="CAFI"):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if not items:
        # Create folder if it doesn't exist
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')
    return items[0].get('id')

def upload_file_to_drive(local_path: str, drive_folder_id: str = None):
    """
    Sube un archivo a Google Drive dentro de la carpeta CAFI,
    sobreescribiendo el archivo si ya existe.
    """
    if not os.path.exists(local_path):
        logger.error(f"El archivo {local_path} no existe localmente.")
        return False
        
    service = get_drive_service()
    if not service:
        return False
        
    try:
        # Usamos nuestra carpeta CAFI por defecto o la especificada
        folder_id = drive_folder_id if drive_folder_id else _get_or_create_folder(service, "CAFI")
        file_name = os.path.basename(local_path)
        
        # Buscar el archivo dentro de la carpeta
        query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        items = results.get('files', [])
        
        mimetype = 'text/markdown' if local_path.endswith('.md') else 'application/json'
        media = MediaFileUpload(local_path, mimetype=mimetype, resumable=True)
        
        if items:
            # Si existe, lo actualizamos (sobrescribimos)
            file_id = items[0].get('id')
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            # Si no, creamos uno nuevo dentro de la carpeta
            file_metadata = {'name': file_name, 'parents': [folder_id]}
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
        return True
    except Exception as e:
        logger.error(f"Error subiendo/actualizando Google Drive: {e}")
        return False
