from celery import shared_task

from worksite.settings import BASE_DIR
from services.common_utils import get_path_to_crop_photo

import os
from PIL import Image
from PIL.Image import Image as Im
from typing import Literal


@shared_task
def make_center_crop(applicant_avatar_path: str) -> Literal[None]:
    """ Функция для обрезки изображения по центру. """

    _center_crop(Image.open(os.path.join(BASE_DIR / applicant_avatar_path))).save(os.path.join(
        get_path_to_crop_photo(applicant_avatar_path)
    ))


def _center_crop(img: Im) -> Im:
    width, height = img.size
    if width / height == 1: return img

    left = (width - min(width, height)) / 2
    top = (height - min(width, height)) / 2
    right = (width + min(width, height)) / 2
    bottom = (height + min(width, height)) / 2

    return img.crop((int(left), int(top), int(right), int(bottom)))
