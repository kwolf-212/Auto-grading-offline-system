import os
import cv2
from datetime import datetime

class RecognitionDebugger:

    def __init__(self,
                 save_dir="debug/digits",
                 enabled=True):

        self.enabled = enabled
        self.save_dir = save_dir

        if enabled:
            os.makedirs(save_dir, exist_ok=True)

    def save_crop(self,
                  image,
                  stage):

        if not self.enabled:
            return

        name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{name}_{stage}.png"

        cv2.imwrite(
            os.path.join(self.save_dir, filename),
            image
        )