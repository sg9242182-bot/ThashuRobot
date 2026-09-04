from vision.camera import Camera
from vision.face_detection import FaceDetector
from vision.tracker import CentroidTracker
from vision.face_recognition import FaceRecognizer
from vision.face_database import FaceDatabase
from vision.vision_core import VisionCore
from hardware.servo_tracking import ServoTracker


cam = Camera().start()

servo = ServoTracker()


detector = FaceDetector(
    "models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
    "models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
)

tracker = CentroidTracker(max_disappeared=30)

recognizer = FaceRecognizer("models/face/w600k_r50.onnx")
database = FaceDatabase()

vision = VisionCore(cam, detector, tracker, recognizer, database, servo=servo)
vision.run()