#!/usr/bin/env python3

from pathlib import Path
import os
import json
import requests
import base64
import subprocess
from ruamel.yaml import YAML, YAMLError
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


# shamefully copied from workbench_utils.py and gutted
def issue_request(
    method: str,
    path: str,
    auth_token: str,
    json_data: dict = None,
) -> requests.Response:
    """Issue the HTTP request to Drupal. Note: calls to non-Drupal URLs
    do not use this function.

    Parameters
    ----------
    method : str
        The HTTP method to be issued for the request, e.g. POST or GET.
    path : str
        Path to the API endpoint that will be used for request.
    auth_token : str
        JWT authentization token
    json_data : dict, optional
        Data to be sent with request body as JSON format, but encoded as a dict.

    Returns
    -------
    requests.Response
    """
    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        try:
            headers = dict()
            headers.update({"User-Agent": "Islandora Workbench Digitalia Wrapper"})
            headers.update({"Authorization": "Bearer " + auth_token})

            url = path

            response = session.request(
                method,
                url,
                allow_redirects=True,
                verify=True,
                headers=headers,
                json=json_data,
                stream=True if method in ["PUT", "POST", "PATCH"] else False,
            )

            return response
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
        ) as error:
            verb = (
                "timed out"
                if isinstance(error, requests.exceptions.Timeout)
                else (
                    f'could not connect to {config["host"]}'
                    if isinstance(error, requests.exceptions.ConnectionError)
                    else "encountered an exception"
                )
            )
            message = f'Workbench {verb} while requesting "{url}".'
            print(message)
            


def process_directory(current_path, parent_id):
    dir_contents = os.listdir(current_path)

    for entry in dir_contents:
        current_full_path = os.path.join(current_path, entry)

        if (Path(current_full_path).is_dir()):
            #parent_id,full_path,subtitle
            #print("NODES: " + str(current_path) + "," + str(current_full_path) + "," +  entry)

            # get parent metadata
            metadata = issue_request("GET", "https://archaeo-vault-devel.phil.muni.cz/node/" + str(parent_id) + "?_format=json", auth_token).json()

            # remove technical and restricted fields
            to_be_removed = {"nid", "uuid", "vid", "revision_timestamp", "revision_uid", "revision_log", "status", "uid", "created", "changed", "promote", "sticky", "default_langcode", "revision_translation_affected", "metatag", "path", "content_translation_source", "content_translation_outdated", "field_model", "field_publisher_dm", "moderation_state"}


            # find empty fields and remove `processed` key from formatted text fields (see https://www.drupal.org/project/drupal/issues/2972988)
            for field, value in metadata.items():
                if len(value) == 0:
                    to_be_removed.add(field)
                else:
                    for subvalue in value:
                        if "processed" in subvalue.keys():
                            subvalue.pop("processed")

            for field in to_be_removed:
                if field in list(metadata):
                    metadata.pop(field)

            metadata["field_member_of"] = [{"target_id": parent_id, "target_type": "node"}]
            metadata["field_subtitle"] = [{"value": os.path.relpath(current_full_path, root_path)}]

            # create intermediary node and get its nid
            post_response = issue_request("POST", "https://archaeo-vault-devel.phil.muni.cz/node?_format=json", auth_token, json_data=metadata).json()
            if post_response.get("nid") is None:
                print("Failed to create new node")
                print(post_response)
                continue


            new_id = post_response.get("nid")[0]["value"]

            process_directory(Path(current_full_path), new_id)

        elif (not Path(current_full_path).match('*/.*')):
            extension = entry.split(".")[-1]

            media_csv_name = None
            for model,value in models.items():
                if extension in value:
                    media_csv_name = "__dm-wrapper_media_csv_" + model + ".csv"
                    break;

            if media_csv_name:
                with open(media_csv_name, mode="a") as media_csv:
                    #parent_id,file
                    media_csv.write(str(parent_id) + "," + str(current_full_path) + "\n")
                    used_files.add(media_csv_name)
            else:
                print("unknown extension in file: " + current_full_path)




yaml = YAML()
root_path = ""
root_id = 0
auth_token = ""


with open("wrapper_config.yml", mode="r") as wrapper_config_file:
    try:
        wrapper_config = yaml.load(wrapper_config_file)
        root_id = wrapper_config.get("root_id")
        root_path = Path(wrapper_config.get("root_path"))
        auth_token = wrapper_config.get("auth_token")
    except YAMLError as exc:
        print("There appears to be a YAML syntax error in your configuration file")
        exit() 



models = dict()
config_dict = dict()
used_files = set()
csv_config_dict = dict()
# ignore raw 3D data for testing
models.update({"3d_model": {"ply", "obj"}})
#models.update({"3d_model": {"ply", "obj", "raw"}})
# TODO: 
models.update({"geospatial_data": {}})
models.update({"audio": {"mp3", "wav", "aac", "flac", "opus"}})
models.update({"video": {"mp4", "mov", "wmv", "avi", "mts", "flv", "f4v", "swf", "mkv", "webm", "ogv", "mpeg"}})
models.update({"csv": {"csv"}})
models.update({"document": {"txt", "rtf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "pdf", "odf", "odg", "odp", "ods", "odt", "fodt", "fods", "fodp", "fodg", "key", "numbers", "pages"}})
models.update({"image": {"png", "gif", "jpg", "jpeg"}})
# leave this as a last resort
# ignore raw 3D data for testing
models.update({"file": {"txt", "rtf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "pdf", "odf", "odg", "odp", "ods", "odt", "fodt", "fods", "fodp", "fodg", "key", "numbers", "pages", "tiff", "tif", "jp2", "xml", "zip", "vtt", "csv", "mdb", "accdb"}})
#models.update({"file": {"txt", "rtf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "pdf", "odf", "odg", "odp", "ods", "odt", "fodt", "fods", "fodp", "fodg", "key", "numbers", "pages", "tiff", "tif", "jp2", "xml", "zip", "vtt", "csv", "mdb", "accdb", "raw"}})

jwt_parsed = json.loads(base64.standard_b64decode(auth_token.split(".")[1]))

id_field = "file"
use_workbench_permissions = True
username = jwt_parsed.get("sub")
host = jwt_parsed.get("iss")
task = "add_media"

config_dict.update({"task": task})
config_dict.update({"host": host})
config_dict.update({"username": username})
# workbench checks for this, ripping it out would be needlessly difficult
config_dict.update({"password": "obviouslynotapassword"})
config_dict.update({"auth_token": auth_token})
config_dict.update({"use_workbench_permissions": use_workbench_permissions})
config_dict.update({"id_field": id_field})
config_dict.update({"media_type_file_fields": {"csv": "field_media_file", "3d_model": "field_media_file", "geospatial_data": "field_media_file"}})

for key in models:
    csv_filename = "__dm-wrapper_media_csv_" + key + ".csv"
    config_filename = "__dm-wrapper_media_config_" + key + ".yml"

    with open(csv_filename, mode="w") as media_csv:
        media_csv.write("node_id,file\n")

    with open(config_filename, mode="w") as media_config:
        config_dict.update({"media_type": key})
        config_dict.update({"input_csv": str(Path(csv_filename).absolute())})
        yaml.dump(config_dict, media_config)
        csv_config_dict.update({csv_filename: config_filename})




# absolute path to dataset root directory; drupal node id of main dataset entry created beforehand
process_directory(root_path, root_id)

for csv in used_files:
    ret = subprocess.run(["./workbench", "--config", csv_config_dict.get(csv), "--check"])
    if ret.returncode == 0:
        subprocess.run(["./workbench", "--config", csv_config_dict.get(csv)])


#ret = subprocess.run(["./workbench", "--config", "media_config_image.yml", "--check"])
#print(ret)
#print(ret.returncode)
