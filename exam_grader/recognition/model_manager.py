
from tensorflow.keras.models import load_model

class ModelManager:

    _digit_model = None

    @classmethod
    def get_digit_model(cls):

        if cls._digit_model is None:

            cls._digit_model = load_model(
                "exam_grader/models/mnist_cnn.h5",
                compile=False
            )

        return cls._digit_model