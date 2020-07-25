import pickle
import os
import requests
import threading

from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
 
def Create_Service(client_secret_file, api_name, api_version, *scopes):
    print(client_secret_file, api_name, api_version, scopes, sep='-')
    CLIENT_SECRET_FILE = client_secret_file
    API_SERVICE_NAME = api_name
    API_VERSION = api_version
    SCOPES = [scope for scope in scopes[0]]
 
    cred = None
 
    pickle_file = f'token_{API_SERVICE_NAME}_{API_VERSION}.pickle'
    # print(pickle_file)
 
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            cred = pickle.load(token)
 
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            cred = flow.run_local_server()
 
        with open(pickle_file, 'wb') as token:
            pickle.dump(cred, token)
 
    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=cred)
        print(API_SERVICE_NAME, 'service created successfully')
        return service
    except Exception as e:
        print(e)
    return None
 
def convert_to_RFC_datetime(year=1900, month=1, day=1, hour=0, minute=0):
    dt = datetime.datetime(year, month, day, hour, minute, 0).isoformat() + 'Z'
    return dt

API_NAME = 'photoslibrary'
API_VERSION = 'v1'
CLIENT_SECRET_FILE = 'photos_api_secret.json'
SCOPES = ['https://www.googleapis.com/auth/photoslibrary']
 
def list_albums(service):
    response = service.albums().list(
        pageSize=50,
        excludeNonAppCreatedData=False
    ).execute()
     
    lstAlbums = response.get('albums')
    nextPageToken = response.get('nextPageToken')

    '''bug here!!!
    while nextPageToken:
        response = service.albums().list(
            pageSize=50,
            excludeNonAppCreatedData=False,
            pageToken=nextPageToken
        ).execute()
        lstAlbums.append(response.get('ablums'))
        nextPageToken = response.get('nextPageToken')
    '''

    if lstAlbums == None:
        return []
    else:
        return lstAlbums

def does_album_title_exist(service, album_title):
    #print(list_albums(service))
    for album in list_albums(service):
        if album['title'] == album_title:
            return True
        
    return False

def get_album_id_by_title(service, album_title):
    for album in list_albums(service):
        if album['title'] == album_title:
            return album['id']

    print('ERROR: invalid album title')
    return ''

def get_album_info(service, album_id):
    response = service.albums().get(albumId=album_id).execute()
    print(response)

def create_album(service, title):
    if does_album_title_exist(service, title):
        return get_album_id_by_title(service, title)
    
    request_body = {
        'album': {'title': title}
    }
    response_album_family_photos = service.albums().create(body=request_body).execute()

    return response_album_family_photos.get('id')

def upload_img(prefix, img_path):
    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'
    token = pickle.load(open('token_photoslibrary_v1.pickle', 'rb'))
    print(f'Uploading {img_path}')
    headers = {
        'Authorization': 'Bearer ' + token.token,
        'Content-type': 'application/octet-stream',
        'X-Goog-Upload-Protocol': 'raw'
    }

    headers['X-Goog-Upload-File-Name'] = (prefix + os.path.basename(img_path)).encode('UTF-8')
     
    img = open(img_path, 'rb').read()
    response = requests.post(upload_url, data=img, headers=headers)

    return response.content.decode('utf-8')


def batch_create_media(service, upload_tokens, album_id=None):
    print('Batch creating media')
    media_items = []
    for token in upload_tokens:
        media_items.append({
                'simpleMediaItem': {
                    'uploadToken': token
                }
            })

    #50 as a batch
    i = 0
    while i < len(media_items):
        upper_bound = min(i+50, len(media_items))
        request_body  = {
            'newMediaItems': media_items[i:upper_bound]
        }
        if album_id != None:
            request_body["albumId"] = album_id
        upload_response = service.mediaItems().batchCreate(body=request_body).execute()

        i += 50

def upload_folder_as_album(service, folder_path):
    print(f'Processing folder: {folder_path}')
    base_name = os.path.basename(folder_path)
    album_title = base_name
    album_id = create_album(service, album_title)

    upload_tokens = []
    for img_name in os.listdir(folder_path):
        upload_tokens.append(upload_img(album_title+'_', os.path.join(folder_path, img_name)))
    batch_create_media(service, upload_tokens, album_id)

if __name__ == '__main__':
    service = Create_Service(CLIENT_SECRET_FILE,API_NAME, API_VERSION, SCOPES)
    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'
    token = pickle.load(open('token_photoslibrary_v1.pickle', 'rb'))

    for folder in sorted(os.listdir(), reverse=True):
        if os.path.isdir(folder) and folder.startswith('['):
            upload_folder_as_album(service, folder)

