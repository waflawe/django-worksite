from celery import shared_task
from worksite.settings import BASE_DIR
import os
from PIL import Image
from PIL.Image import Image as Im
from typing import Literal


@shared_task
def make_center_crop(applicant_avatar_path) -> Literal[None]:
    """ Функция для обрезки изображения по центру. """

    t = applicant_avatar_path.split(".")
    new_crop_image_path = BASE_DIR / (t[0] + "_crop." + t[1])
    _center_crop(Image.open(os.path.join(BASE_DIR / applicant_avatar_path))).save(os.path.join(
        new_crop_image_path
    ))


def _center_crop(img: Im) -> Im:
    width, height = img.size
    if width / height == 1: return img

    left = (width - min(width, height)) / 2
    top = (height - min(width, height)) / 2
    right = (width + min(width, height)) / 2
    bottom = (height + min(width, height)) / 2

    return img.crop((int(left), int(top), int(right), int(bottom)))
