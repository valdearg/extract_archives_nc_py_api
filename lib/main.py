"""Simplest example of files_dropdown_menu and notification API."""

import json
import os
import tempfile
import typing
import time
import shutil
from base64 import b64encode, b64decode
from random import choice
from string import ascii_lowercase, ascii_uppercase, digits
from urllib.parse import quote

import cv2
import httpx
import imageio
import numpy
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, responses, status
from pydantic import BaseModel
from pygifsicle import optimize
from requests import Response

import zipfile
from pathlib import Path
from pyunpack import Archive

APP = FastAPI()


class UiActionFileInfo(BaseModel):
    fileId: int
    name: str
    directory: str
    etag: str
    mime: str
    fileType: str
    size: int
    favorite: str
    permissions: int
    mtime: int
    userId: str
    shareOwner: typing.Optional[str]
    shareOwnerId: typing.Optional[str]
    instanceId: typing.Optional[str]


def extract_folder_name(zip_filename, nc_file_path):
    # Open the zip file
    try:
        with zipfile.ZipFile(zip_filename, "r") as zip_ref:
            # Get a list of all the files and folders at the first level
            files = [item for item in zip_ref.namelist() if not "/" in item]
            folders = [item for item in zip_ref.namelist() if "/" in item]

            root_folders_array = []

            for root_folder in folders:
                root_folders_array.append(root_folder.split("/")[0])

            root_folders_array = list(set(root_folders_array))
            root_folders_array = sorted(root_folders_array)

            print(f"Contains: {len(files)} files on the root level")
            print(f"Contains: {len(folders)} files in folders on the root level")
            print(f"Contains: {len(root_folders_array)} folders on the root level")

            print(f"Parent name: {nc_file_path.parent.name}")
            print(f"zip_file_path.stem: {nc_file_path.stem}")

            if len(root_folders_array) >= 1 and len(files) >= 1:
                # folder_name = zip_file_path.split("/")[-1]
                folder_name = os.path.splitext(str(nc_file_path))[0]
                return folder_name
            elif (
                len(root_folders_array) == 1
                and nc_file_path.parent.name == nc_file_path.stem
            ):

                print(
                    f"ZIP folder name is the same as the folder name: {nc_file_path.parent}"
                )
                return nc_file_path.parent.parent

            elif len(root_folders_array) >= 1:
                return nc_file_path.parent
            else:
                # folder_name = zip_file_path.split("/")[-1]
                folder_name = os.path.splitext(str(nc_file_path))[0]
                return folder_name
    except Exception as ex:
        print("Error reading zip file!")
        print(ex)
        return None


def random_string(size: int) -> str:
    return "".join(choice(ascii_lowercase + ascii_uppercase + digits) for _ in range(size))


def get_nc_url() -> str:
    return os.environ["NEXTCLOUD_URL"].removesuffix("/index.php").removesuffix("/")


def sign_request(headers: dict, user="") -> None:
    headers["AUTHORIZATION-APP-API"] = b64encode(f"{user}:{os.environ['APP_SECRET']}".encode("UTF=8"))
    headers["EX-APP-ID"] = os.environ["APP_ID"]
    headers["EX-APP-VERSION"] = os.environ["APP_VERSION"]
    headers["OCS-APIRequest"] = "true"


def sign_check(request: Request) -> str:
    headers = {
        "AA-VERSION": request.headers["AA-VERSION"],
        "EX-APP-ID": request.headers["EX-APP-ID"],
        "EX-APP-VERSION": request.headers["EX-APP-VERSION"],
        "AUTHORIZATION-APP-API": request.headers.get("AUTHORIZATION-APP-API", ""),
    }
    # AA-VERSION contains AppAPI version, for now it can be only one version, so no handling of it.
    if headers["EX-APP-ID"] != os.environ["APP_ID"]:
        raise ValueError(f"Invalid EX-APP-ID:{headers['EX-APP-ID']} != {os.environ['APP_ID']}")

    if headers["EX-APP-VERSION"] != os.environ["APP_VERSION"]:
        raise ValueError(f"Invalid EX-APP-VERSION:{headers['EX-APP-VERSION']} <=> {os.environ['APP_VERSION']}")

    auth_aa = b64decode(headers.get("AUTHORIZATION-APP-API", "")).decode("UTF-8")
    username, app_secret = auth_aa.split(":", maxsplit=1)
    if app_secret != os.environ["APP_SECRET"]:
        raise ValueError(f"Invalid APP_SECRET:{app_secret} != {os.environ['APP_SECRET']}")
    return username


def ocs_call(
        method: str,
        path: str,
        params: typing.Optional[dict] = None,
        json_data: typing.Optional[typing.Union[dict, list]] = None,
        **kwargs,
):
    method = method.upper()
    if params is None:
        params = {}
    params.update({"format": "json"})
    headers = kwargs.pop("headers", {})
    data_bytes = None
    if json_data is not None:
        headers.update({"Content-Type": "application/json"})
        data_bytes = json.dumps(json_data).encode("utf-8")
    sign_request(headers, kwargs.get("user", ""))
    return httpx.request(
        method,
        url=get_nc_url() + path,
        params=params,
        content=data_bytes,
        headers=headers,
        timeout=30
    )


def dav_call(method: str, path: str, data: typing.Optional[typing.Union[str, bytes]] = None, **kwargs):
    headers = kwargs.pop("headers", {})
    data_bytes = None
    if data is not None:
        data_bytes = data.encode("UTF-8") if isinstance(data, str) else data
    path = quote("/remote.php/dav" + path)
    folder_path = path.rsplit('/', 1)[0]
    sign_request(headers, kwargs.get("user", ""))

    # creating the folder
    httpx.request(
        "MKCOL",
        url=get_nc_url() + folder_path,
        headers=headers,
        timeout=3000
    )

    # performing the request
    return httpx.request(
        method,
        url=get_nc_url() + path,
        content=data_bytes,
        headers=headers,
        timeout=3000
    )


def nc_log(log_lvl: int, content: str):
    print(content)
    ocs_call("POST", "/ocs/v1.php/apps/app_api/api/v1/log", json_data={"level": log_lvl, "message": content})


def create_notification(user_id: str, subject: str, message: str):
    params: dict = {
        "params": {
            "object": "app_api",
            "object_id": random_string(56),
            "subject_type": "app_api_ex_app",
            "subject_params": {
                "rich_subject": subject,
                "rich_subject_params": {},
                "rich_message": message,
                "rich_message_params": {},
            },
        }
    }
    ocs_call(
        method="POST", path=f"/ocs/v1.php/apps/app_api/api/v1/notification", json_data=params, user=user_id
    )


def convert_video_to_gif(input_file: UiActionFileInfo, user_id: str):
    # save_path = path.splitext(input_file.user_path)[0] + ".gif"
    if input_file.directory == "/":
        dav_get_file_path = f"/files/{user_id}/{input_file.name}"
    else:
        dav_get_file_path = f"/files/{user_id}{input_file.directory}/{input_file.name}"
    dav_save_file_path = os.path.splitext(dav_get_file_path)[0] + ".gif"
    # ===========================================================
    nc_log(2, f"Processing:{input_file.name}")
    try:
        with tempfile.NamedTemporaryFile(mode="w+b") as tmp_in:
            r = dav_call("GET", dav_get_file_path, user=user_id)
            tmp_in.write(r.content)
            # ============================================
            nc_log(2, "File downloaded")
            tmp_in.flush()
            cap = cv2.VideoCapture(tmp_in.name)
            with tempfile.NamedTemporaryFile(mode="w+b", suffix=".gif") as tmp_out:
                image_lst = []
                previous_frame = None
                skip = 0
                while True:
                    skip += 1
                    ret, frame = cap.read()
                    if frame is None:
                        break
                    if skip == 2:
                        skip = 0
                        continue
                    if previous_frame is not None:
                        diff = numpy.mean(previous_frame != frame)
                        if diff < 0.91:
                            continue
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image_lst.append(frame_rgb)
                    previous_frame = frame
                    if len(image_lst) > 60:
                        break
                cap.release()
                imageio.mimsave(tmp_out.name, image_lst)
                optimize(tmp_out.name)
                nc_log(2, "GIF is ready")
                tmp_out.seek(0)
                dav_call("PUT", dav_save_file_path, data=tmp_out.read(), user=user_id)
                # ==========================================
                nc_log(2, "Result uploaded")
                create_notification(
                    user_id,
                    f"{input_file.name} finished!",
                    f"{os.path.splitext(input_file.name)[0] + '.gif'} is waiting for you!",
                )
    except Exception as e:
        nc_log(3, "ExApp exception:" + str(e))
        create_notification(user_id, "Error occurred", "Error information was written to log file")


def extract_archive(input_file: UiActionFileInfo, user_id: str):
    # save_path = path.splitext(input_file.user_path)[0] + ".gif"
    if input_file.directory == "/":
        dav_get_file_path = f"/files/{user_id}/{input_file.name}"
    else:
        dav_get_file_path = f"/files/{user_id}{input_file.directory}/{input_file.name}"
    dav_save_file_path = os.path.splitext(dav_get_file_path)[0] + ".gif"
    # ===========================================================
    nc_log(2, f"Processing: {input_file.name}")
    nc_log(2, f"Full path is: {dav_get_file_path}")

    temp_path = tempfile.gettempdir()
    print(f"Temp path is: {temp_path}")

    downloaded_file = os.path.join(temp_path, input_file.name)

    try:
        with open(downloaded_file, "wb") as tmp_in:
            r = dav_call("GET", dav_get_file_path, user=user_id)
            tmp_in.write(r.content)
            # ============================================
            nc_log(2, "File downloaded")
            tmp_in.flush()

        destination_path = os.path.join(temp_path, "Extracted")

        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        print(f"Extracting archive {input_file.name}")
        try:
            Archive(downloaded_file).extractall(destination_path)
        except Exception as ex:
            print(f"Error extracting archive: {ex}")

        for filename in Path(destination_path).rglob("*.*"):
            print(f"File: {str(filename)}")
            # print(f"DAV save path originally: {dav_save_file_path}")
            dav_save_file_path = str(filename).replace(destination_path, f'/files/{user_id}{input_file.directory}/')
            # print(f"DAV save path replacing destination path: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("\\", "/")
            # print(f"Replacing the forward slashes: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("//", "/")
            print(f"Final DAV path: {dav_save_file_path}")
            dav_call("PUT", dav_save_file_path, data=open(str(filename), "rb").read(), user=user_id)

        try:
            print("Removing original file")
            os.remove(downloaded_file)
        except Exception as ex:
            print(f"Error removing file: {ex}")

        try:
            shutil.rmtree(destination_path)
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))

        nc_log(2, "Result uploaded")
        create_notification(
            user_id,
            f"{input_file.name} finished!",
            "Extracted file(s) are waiting for you!",
        )

    except Exception as e:
        nc_log(3, "ExApp exception:" + str(e))
        create_notification(user_id, "Error occurred", "Error information was written to log file")


def extract_archive_to_parent(input_file: UiActionFileInfo, user_id: str):
    # save_path = path.splitext(input_file.user_path)[0] + ".gif"
    if input_file.directory == "/":
        dav_get_file_path = f"/files/{user_id}/{input_file.name}"
    else:
        dav_get_file_path = f"/files/{user_id}{input_file.directory}/{input_file.name}"

    # ===========================================================
    nc_log(2, f"Processing: {input_file.name}")
    nc_log(2, f"Full path is: {dav_get_file_path}")

    temp_path = tempfile.gettempdir()
    print(f"Temp path is: {temp_path}")

    downloaded_file = os.path.join(temp_path, input_file.name)

    try:
        with open(downloaded_file, "wb") as tmp_in:
            r = dav_call("GET", dav_get_file_path, user=user_id)
            tmp_in.write(r.content)
            # ============================================
            nc_log(2, "File downloaded")
            tmp_in.flush()

        destination_path = os.path.join(temp_path, "Extracted")

        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        print(f"Extracting archive {input_file.name}")
        try:
            Archive(downloaded_file).extractall(destination_path)
        except Exception as ex:
            print(f"Error extracting archive: {ex}")

        for filename in Path(destination_path).rglob("*.*"):
            print(f"File: {str(filename)}")
            # print(f"DAV save path originally: {dav_save_file_path}")
            parent_folder = input_file.directory.rsplit('/', 1)[0]
            dav_save_file_path = str(filename).replace(destination_path, f'/files/{user_id}{parent_folder}/')
            # print(f"DAV save path replacing destination path: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("\\", "/")
            # print(f"Replacing the forward slashes: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("//", "/")
            print(f"Final DAV path: {dav_save_file_path}")
            dav_call("PUT", dav_save_file_path, data=open(str(filename), "rb").read(), user=user_id)

        try:
            print("Removing original file")
            os.remove(downloaded_file)
        except Exception as ex:
            print(f"Error removing file: {ex}")

        try:
            shutil.rmtree(destination_path)
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))

        nc_log(2, "Result uploaded")
        create_notification(
            user_id,
            f"{input_file.name} finished!",
            "Extracted file(s) are waiting for you!",
        )

    except Exception as e:
        nc_log(3, "ExApp exception:" + str(e))
        create_notification(user_id, "Error occurred", "Error information was written to log file")


def extract_archive_auto_testing(input_file: UiActionFileInfo, user_id: str):
    # save_path = path.splitext(input_file.user_path)[0] + ".gif"
    if input_file.directory == "/":
        dav_get_file_path = f"/files/{user_id}/{input_file.name}"
    else:
        dav_get_file_path = f"/files/{user_id}{input_file.directory}/{input_file.name}"

    # ===========================================================
    nc_log(2, f"Processing: {input_file.name}")
    nc_log(2, f"Full path is: {dav_get_file_path}")

    temp_path = tempfile.gettempdir()

    downloaded_file = os.path.join(temp_path, input_file.name)

    date_and_time = time.strftime("%Y%m%d%H%M%S")

    try:
        with open(downloaded_file, "wb") as tmp_in:
            r = dav_call("GET", dav_get_file_path, user=user_id)
            tmp_in.write(r.content)
            # ============================================
            nc_log(2, "File downloaded")
            tmp_in.flush()

        destination_path = os.path.join(temp_path, "Extracted", date_and_time)
        dav_destination_path = None

        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        print(f"Checking dest path for archive {input_file.name}")
        try:
            dav_destination_path = extract_folder_name(downloaded_file, Path(dav_get_file_path))
            print(f"Extracting to: {dav_destination_path}")
        except Exception as ex:
            print(f"Error extracting archive: {ex}")

        print(f"Extracting archive {input_file.name}")
        try:
            Archive(downloaded_file).extractall(destination_path)
        except Exception as ex:
            print(f"Error extracting archive: {ex}")

        for filename in Path(destination_path).rglob("*.*"):
            print(f"File: {str(filename)}")
            # print(f"DAV save path originally: {dav_save_file_path}")
            dav_save_file_path = str(filename).replace(destination_path, f'{dav_destination_path}/')
            # print(f"DAV save path replacing destination path: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("\\", "/")
            # print(f"Replacing the forward slashes: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("//", "/")
            print(f"Final DAV path: {dav_save_file_path}")
            dav_call("PUT", dav_save_file_path, data=open(str(filename), "rb").read(), user=user_id)
            os.remove(str(filename))

        try:
            print("Removing original file")
            os.remove(downloaded_file)
        except Exception as ex:
            print(f"Error removing file: {ex}")

        nc_log(2, "Result uploaded")
        create_notification(
            user_id,
            f"{input_file.name} finished!",
            "Extracted file(s) are waiting for you!",
        )

    except Exception as e:
        nc_log(3, "ExApp exception:" + str(e))
        create_notification(user_id, "Error occurred", "Error information was written to log file")


@APP.post("/extract_to_here")
def extract_to_here(
        file: UiActionFileInfo,
        request: Request,
        background_tasks: BackgroundTasks,
):
    try:
        user_id = sign_check(request)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    background_tasks.add_task(extract_archive, file, user_id)
    return Response()


@APP.post("/extract_to_parent")
def extract_to_here(
        file: UiActionFileInfo,
        request: Request,
        background_tasks: BackgroundTasks,
):
    try:
        user_id = sign_check(request)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    # background_tasks.add_task(extract_archive_to_parent, file, user_id)
    background_tasks.add_task(extract_archive_auto_testing, file, user_id)
    return Response()


@APP.put("/enabled")
def enabled_callback(
        enabled: bool,
        request: Request,
):
    print("Running enabled")

    try:
        sign_check(request)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    print(f"enabled={enabled}")
    try:
        r = ""
        if enabled:
            result = ocs_call(
                "POST",
                "/ocs/v1.php/apps/app_api/api/v1/ui/files-actions-menu",
                json_data={
                    "name": "extract_to_here",
                    "displayName": "Extract HERE",
                    "mime": "application/zip",
                    "permissions": 31,
                    "actionHandler": "/extract_to_here",
                },
            )
            response_data = json.loads(result.text)
            ocs_meta = response_data["ocs"]["meta"]
            if ocs_meta["status"] != "ok":
                r = f"error: {ocs_meta['message']}"
                print(f"Error from the files-actions-menu call: {ocs_meta['message']}")

            result = ocs_call(
                "POST",
                "/ocs/v1.php/apps/app_api/api/v1/ui/files-actions-menu",
                json_data={
                    "name": "extract_to_here",
                    "displayName": "Extract TO PARENT",
                    "mime": "application/zip",
                    "permissions": 31,
                    "actionHandler": "/extract_to_parent",
                },
            )
            response_data = json.loads(result.text)
            ocs_meta = response_data["ocs"]["meta"]
            if ocs_meta["status"] != "ok":
                r = f"error: {ocs_meta['message']}"
                print(f"Error from the files-actions-menu call: {ocs_meta['message']}")
        else:
            ocs_call(
                "DELETE",
                "/ocs/v1.php/apps/app_api/api/v1/ui/files-actions-menu",
                json_data={"name": "extract_to_here"},
            )

            ocs_call(
                "DELETE",
                "/ocs/v1.php/apps/app_api/api/v1/ui/files-actions-menu",
                json_data={"name": "extract_to_parent"},
            )
    except Exception as e:
        r = str(e)
    print(f"enabled={enabled} -> {r}")
    return responses.JSONResponse(content={"error": r}, status_code=200)


@APP.get("/heartbeat")
def heartbeat_callback():
    return responses.JSONResponse(content={"status": "ok"}, status_code=200)


if __name__ == "__main__":
    main_temp_path = tempfile.gettempdir()
    main_destination_path = os.path.join(main_temp_path, "Extracted")

    try:
        shutil.rmtree(main_destination_path)
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))

    uvicorn.run(
        "main:APP", host=os.environ.get("APP_HOST", "127.0.0.1"), port=int(os.environ["APP_PORT"]), log_level="trace"
    )
