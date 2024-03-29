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


def extract_to_auto(input_file: FsNode, nc: NextcloudApp, extract_to="auto"):
    print(input_file)

    input_file_name = input_file.user_path.split("\\")[-1]

    print(f"input_file_name path: {input_file_name}")

    dav_file_path = input_file.user_path.replace("\\", "/")
    user_id, dav_file_path = dav_file_path.split("/", 1)
    print(f"DAV file path: {dav_file_path}")

    temp_path = tempfile.gettempdir()

    downloaded_file = os.path.join(temp_path, input_file_name)

    nc.log(LogLvl.WARNING, f"Processing: {input_file.user_path} -> {downloaded_file}")

    date_and_time = time.strftime("%Y%m%d%H%M%S")

    try:
        with open(downloaded_file, "wb") as tmp_in:
            nc.files.download2stream(path=dav_file_path, fp=tmp_in)
            nc.log(LogLvl.WARNING, "File downloaded")

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

            print(f"Extracting to: {dav_destination_path}")
        except Exception as ex:
            print(f"ERROR: Checking dest path for archive: {ex}")

        print(f"Extracting archive {input_file.name}")
        try:
            Archive(downloaded_file).extractall(destination_path)
        except Exception as ex:
            print(f"Error extracting archive: {ex}")

        for filename in Path(destination_path).rglob("*.*"):
            print(f"File: {str(filename)}")
            # print(f"DAV save path originally: {dav_save_file_path}")
            dav_save_file_path = str(filename).replace(
                destination_path, f"{dav_destination_path}/"
            )
            # print(f"DAV save path replacing destination path: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("\\", "/")
            # print(f"Replacing the forward slashes: {dav_save_file_path}")
            dav_save_file_path = dav_save_file_path.replace("//", "/")

            dav_save_file_path = dav_save_file_path.split("/", 1)[-1]

            print(f"Final DAV path: {dav_save_file_path}")

            nc.files.upload_stream(path=dav_save_file_path, fp=filename)
            os.remove(str(filename))

        try:
            print("Removing original file")
            os.remove(downloaded_file)
        except Exception as ex:
            print(f"Error removing file: {ex}")

        nc.log(LogLvl.WARNING, "Result uploaded")
        print(f"{input_file_name} finished!", f"{input_file_name} is waiting for you!")
        nc.notifications.create(
            subject=f"{input_file_name} finished!",
            message=f"{input_file_name} is waiting for you!",
        )

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
    nc: Annotated[NextcloudApp, Depends(nc_app)],
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(extract_to_auto, file.to_fs_node(), nc)
    return Response()


@APP.post("/extract_to_parent")
async def endpoint_extract_to_parent(
    file: UiActionFileInfo,
    nc: Annotated[NextcloudApp, Depends(nc_app)],
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(extract_to_auto, file.to_fs_node(), nc, "parent")
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
