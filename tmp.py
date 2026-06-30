import os

file_path = "MNIST_keras_CNN.h5"

print("exists :", os.path.exists(file_path))
print("size   :", os.path.getsize(file_path))

with open(file_path, "rb") as f:
    print(f.read(32))