"""Simplest example of files_dropdown_menu + notification."""

import json
import os
import time
import tempfile
from contextlib import asynccontextmanager
from os import path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI
from requests import Response

from nc_py_api import FsNode, NextcloudApp
from nc_py_api.ex_app import (
    AppAPIAuthMiddleware,
    LogLvl,
    UiActionFileInfo,
    nc_app,
    run_app,
    set_handlers,
)

from base64 import b64encode, b64decode
import httpx
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
import zipfile
from pathlib import Path
from pyunpack import Archive


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_handlers(app, enabled_handler)
    yield


APP = FastAPI(lifespan=lifespan)
APP.add_middleware(AppAPIAuthMiddleware)


def random_string(size: int) -> str:
    return "".join(
        choice(ascii_lowercase + ascii_uppercase + digits) for _ in range(size)
    )


def get_nc_url() -> str:
    return os.environ["NEXTCLOUD_URL"].removesuffix("/index.php").removesuffix("/")


def sign_request(headers: dict, user="") -> None:
    headers["AUTHORIZATION-APP-API"] = b64encode(
        f"{user}:{os.environ['APP_SECRET']}".encode("UTF=8")
    )
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
        raise ValueError(
            f"Invalid EX-APP-ID:{headers['EX-APP-ID']} != {os.environ['APP_ID']}"
        )

    if headers["EX-APP-VERSION"] != os.environ["APP_VERSION"]:
        raise ValueError(
            f"Invalid EX-APP-VERSION:{headers['EX-APP-VERSION']} <=> {os.environ['APP_VERSION']}"
        )

    auth_aa = b64decode(headers.get("AUTHORIZATION-APP-API", "")).decode("UTF-8")
    username, app_secret = auth_aa.split(":", maxsplit=1)
    if app_secret != os.environ["APP_SECRET"]:
        raise ValueError(
            f"Invalid APP_SECRET:{app_secret} != {os.environ['APP_SECRET']}"
        )
    return username


def dav_call(
    method: str,
    path: str,
    nc: NextcloudApp,
    data: typing.Optional[typing.Union[str, bytes]] = None,
    **kwargs,
):
    headers = kwargs.pop("headers", {})
    data_bytes = None
    if data is not None:
        data_bytes = data.encode("UTF-8") if isinstance(data, str) else data
    path = quote("/remote.php/dav" + path)

    print(f"Path quoted: {path}")

    nc.log(LogLvl.WARNING, f"Path quoted: {path}")

    folder_path = path.rsplit("/", 1)[0]
    print(f"Folder path quoted: {folder_path}")

    nc.log(LogLvl.WARNING, f"Folder path quoted: {folder_path}")

    sign_request(headers, kwargs.get("user", ""))

    nc.log(LogLvl.WARNING, f"Full URL: {get_nc_url() + folder_path}")

    # creating the folder
    httpx.request(
        "MKCOL", url=get_nc_url() + folder_path, headers=headers, timeout=3000
    )

    # performing the request
    return httpx.request(
        method,
        url=get_nc_url() + path,
        content=data_bytes,
        headers=headers,
        timeout=3000,
    )


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
        timeout=30,
    )


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
        method="POST",
        path="/ocs/v1.php/apps/app_api/api/v1/notification",
        json_data=params,
        user=user_id,
    )


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
            elif len(root_folders_array) > 1:
                print("Number of folders > 1, using zip file name!")
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


def extract_to_auto(input_file: FsNode, nc: NextcloudApp, user_id, extract_to="auto"):
    print(input_file)
    nc.log(LogLvl.WARNING, f"Input_file: {input_file}")

    print(f"user: {user_id}")
    print(f"Directory separator: {os.sep}")

    input_file_name = input_file.user_path.split(os.sep)[-1]

    nc.log(LogLvl.WARNING, f"input_file_name path: {input_file_name}")
    print(f"input_file_name path: {input_file_name}")

    dav_file_path = input_file.user_path.replace("\\", "/")
    # user_id, dav_file_path = dav_file_path.split("/", 1)[]

    nc.log(LogLvl.WARNING, f"DAV file path: {dav_file_path}")
    print(f"DAV file path: {dav_file_path}")

    temp_path = tempfile.gettempdir()

    downloaded_file = os.path.join(temp_path, input_file_name)

    nc.log(LogLvl.WARNING, f"Processing: {input_file.user_path} -> {downloaded_file}")

    date_and_time = time.strftime("%Y%m%d%H%M%S")

    try:
        with open(downloaded_file, "wb") as tmp_in:
            try:
                nc.files.download2stream(path=dav_file_path, fp=tmp_in)
                nc.log(LogLvl.WARNING, "File downloaded")
            except Exception as ex:
                nc.log(LogLvl.ERROR, f"Error downloading file: {ex}")

            tmp_in.flush()

        destination_path = os.path.join(temp_path, "Extracted", date_and_time)
        dav_destination_path = None

        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

        print(f"Checking dest path for archive {input_file.name}")
        try:
            if extract_to == "auto":
                dav_destination_path = extract_folder_name(
                    downloaded_file, Path(input_file.user_path)
                )
            elif extract_to == "parent":
                dav_destination_path = Path(input_file.user_path).parent

            if str(dav_destination_path).startswith(user_id):
                dav_destination_path = str(dav_destination_path).split("/", 1)[-1]

            nc.log(LogLvl.WARNING, f"Extracting to: {dav_destination_path}")
            print(f"Extracting to: {dav_destination_path}")
        except Exception as ex:
            nc.log(LogLvl.WARNING, f"ERROR: Checking dest path for archive: {ex}")
            print(f"ERROR: Checking dest path for archive: {ex}")

        print(f"Extracting archive {input_file.name}")
        try:
            Archive(downloaded_file).extractall(destination_path)
        except Exception as ex:
            nc.log(LogLvl.WARNING, f"Error extracting archive: {ex}")
            print(f"Error extracting archive: {ex}")

        for filename in Path(destination_path).rglob("*.*"):
            nc.log(LogLvl.WARNING, f"File: {str(filename)}")
            print(f"File: {str(filename)}")
            # print(f"DAV save path originally: {dav_save_file_path}")
            dav_save_file_path = str(filename).replace(
                destination_path, f"{dav_destination_path}/"
            )
            # print(f"DAV save path replacing destination path: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("\\", "/")
            # print(f"Replacing the forward slashes: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("//", "/")

            if dav_save_file_path.startswith(user_id):
                dav_save_file_path = dav_save_file_path.split("/", 1)[-1]

            nc.log(LogLvl.WARNING, f"Final DAV path: {dav_save_file_path}")
            print(f"Final DAV path: {dav_save_file_path}")

            nc.log(LogLvl.WARNING, f"Uploading: {filename} to: {dav_save_file_path}")
            try:
                nc.files.upload_stream(path=dav_save_file_path, fp=filename)
            except Exception as ex:
                nc.log(LogLvl.WARNING, "Error uploading, using alt")
                dav_save_file_path = f"/files/{user_id}/{dav_save_file_path}"

                nc.log(
                    LogLvl.WARNING, f"dav_save_file_path becomes: {dav_save_file_path}"
                )

                dav_call(
                    "PUT",
                    dav_save_file_path,
                    nc,
                    data=open(str(filename), "rb").read(),
                    user=user_id,
                )

                nc.log(LogLvl.ERROR, f"ERROR: {ex}")

            os.remove(str(filename))

        try:
            nc.log(LogLvl.WARNING, "Removing original file")
            print("Removing original file")
            os.remove(downloaded_file)
        except Exception as ex:
            nc.log(LogLvl.WARNING, f"Error removing file: {ex}")
            print(f"Error removing file: {ex}")

        nc.log(LogLvl.WARNING, "Result uploaded")
        print(f"{input_file_name} finished!", f"{input_file_name} is waiting for you!")

        try:
            nc.notifications.create(
                subject=f"{input_file_name} finished!",
                message=f"{input_file_name} is waiting for you!",
            )
        except Exception as ex:
            create_notification(
                user_id,
                f"{input_file_name} finished!",
                "Extracted file(s) are waiting for you!",
            )

    except Exception as e:
        nc.log(LogLvl.ERROR, str(e))
        print("Error occurred", "Error information was written to log file")


@APP.post("/extract_to_auto")
async def endpoint_extract_to_auto(
    file: UiActionFileInfo,
    request: Request,
    nc: Annotated[NextcloudApp, Depends(nc_app)],
    background_tasks: BackgroundTasks,
):
    try:
        user_id = sign_check(request)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    background_tasks.add_task(extract_to_auto, file.to_fs_node(), nc, user_id, "auto")
    return Response()


@APP.post("/extract_to_parent")
async def endpoint_extract_to_parent(
    file: UiActionFileInfo,
    request: Request,
    nc: Annotated[NextcloudApp, Depends(nc_app)],
    background_tasks: BackgroundTasks,
):
    try:
        user_id = sign_check(request)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    background_tasks.add_task(extract_to_auto, file.to_fs_node(), nc, user_id, "parent")
    return Response()


def enabled_handler(enabled: bool, nc: NextcloudApp) -> str:
    print(f"enabled={enabled}")
    try:
        if enabled:
            nc.ui.files_dropdown_menu.register(
                "extract_to_here",
                "Extract To Auto",
                "/extract_to_auto",
                mime="application/zip",
            )

            nc.ui.files_dropdown_menu.register(
                "extract_to_parent",
                "Extract To Parent",
                "/extract_to_parent",
                mime="application/zip",
            )
        else:
            nc.ui.files_dropdown_menu.unregister("extract_to_here")
            nc.ui.files_dropdown_menu.unregister("extract_to_parent")
    except Exception as e:
        return str(e)
    return ""


if __name__ == "__main__":
    main_temp_path = tempfile.gettempdir()
    main_destination_path = os.path.join(main_temp_path, "Extracted")

    try:
        shutil.rmtree(main_destination_path)
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))

    run_app(
        "main:APP",
        log_level="trace",
    )
