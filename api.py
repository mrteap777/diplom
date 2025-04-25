from flask import Flask, request, jsonify
import cv2
import numpy as np
import tempfile
import os
import time
import mediapipe as mp
from typing import List, Dict, Tuple

app = Flask(__name__)

# Инициализация MediaPipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# Настройки по умолчанию
DEFAULT_LANDMARK_COLOR = (0, 255, 0)
DEFAULT_CONNECTION_COLOR = (255, 0, 0)

def count_pushups(landmarks, prev_state, counter):
    """Алгоритм подсчета отжиманий"""
    left_shoulder = landmarks.landmark[mp_pose.PoseLandmark.LEFT_SHOULDER]
    right_shoulder = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    left_elbow = landmarks.landmark[mp_pose.PoseLandmark.LEFT_ELBOW]
    right_elbow = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_ELBOW]
    
    shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
    elbow_y = (left_elbow.y + right_elbow.y) / 2
    
    current_state = "down" if elbow_y > shoulder_y else "up"
    
    if prev_state == "up" and current_state == "down":
        counter += 1
        prev_state = "down"
    elif current_state == "up":
        prev_state = "up"
    
    return counter, prev_state

def count_squats(landmarks, prev_state, counter):
    """Алгоритм подсчета приседаний"""
    left_hip = landmarks.landmark[mp_pose.PoseLandmark.LEFT_HIP]
    right_hip = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_HIP]
    left_knee = landmarks.landmark[mp_pose.PoseLandmark.LEFT_KNEE]
    right_knee = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_KNEE]
    
    hip_y = (left_hip.y + right_hip.y) / 2
    knee_y = (left_knee.y + right_knee.y) / 2
    
    current_state = "down" if knee_y > hip_y else "up"
    
    if prev_state == "up" and current_state == "down":
        counter += 1
        prev_state = "down"
    elif current_state == "up":
        prev_state = "up"
    
    return counter, prev_state

def count_pullups(landmarks, prev_state, counter):
    """Алгоритм подсчета подтягиваний"""
    left_shoulder = landmarks.landmark[mp_pose.PoseLandmark.LEFT_SHOULDER]
    right_shoulder = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    left_elbow = landmarks.landmark[mp_pose.PoseLandmark.LEFT_ELBOW]
    right_elbow = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_ELBOW]
    
    shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
    elbow_y = (left_elbow.y + right_elbow.y) / 2
    
    current_state = "up" if elbow_y < shoulder_y else "down"
    
    if prev_state == "down" and current_state == "up":
        counter += 1
        prev_state = "up"
    elif current_state == "down":
        prev_state = "down"
    
    return counter, prev_state

def count_plank(landmarks, start_time, duration):
    """Алгоритм подсчета времени планки"""
    # Проверяем правильность положения тела
    left_shoulder = landmarks.landmark[mp_pose.PoseLandmark.LEFT_SHOULDER]
    right_shoulder = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    left_hip = landmarks.landmark[mp_pose.PoseLandmark.LEFT_HIP]
    right_hip = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_HIP]
    
    # Проверяем, что плечи и бедра находятся примерно на одной линии
    shoulder_hip_diff = abs((left_shoulder.y + right_shoulder.y)/2 - (left_hip.y + right_hip.y)/2)
    
    if shoulder_hip_diff < 0.1:  # Эмпирически подобранное значение
        return time.time() - start_time
    return duration

def count_lunges(landmarks, prev_state, counter):
    """Алгоритм подсчета выпадов"""
    left_knee = landmarks.landmark[mp_pose.PoseLandmark.LEFT_KNEE]
    right_knee = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_KNEE]
    left_ankle = landmarks.landmark[mp_pose.PoseLandmark.LEFT_ANKLE]
    right_ankle = landmarks.landmark[mp_pose.PoseLandmark.RIGHT_ANKLE]
    
    # Определяем, какая нога впереди
    if left_knee.x < right_knee.x:
        front_knee = left_knee
        back_knee = right_knee
    else:
        front_knee = right_knee
        back_knee = left_knee
    
    knee_ankle_diff = abs(front_knee.x - (left_ankle.x if front_knee == left_knee else right_ankle.x))
    
    current_state = "down" if knee_ankle_diff < 0.1 else "up"
    
    if prev_state == "up" and current_state == "down":
        counter += 1
        prev_state = "down"
    elif current_state == "up":
        prev_state = "up"
    
    return counter, prev_state

@app.route('/process_video', methods=['POST'])
def process_video_api():
    """API endpoint для обработки видео"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    exercise_ranges = request.form.get('exercise_ranges', [])
    model_complexity = int(request.form.get('model_complexity', 1))
    
    # Сохраняем временный файл
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.mp4")
    output_path = os.path.join(temp_dir, "output.mp4")
    
    video_file.save(input_path)
    
    # Преобразуем exercise_ranges из строки в список кортежей
    try:
        exercise_ranges = eval(exercise_ranges) if exercise_ranges else []
    except:
        exercise_ranges = []
    
    # Обработка видео
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    processed_frames = 0
    start_time = time.time()
    
    # Переводим интервалы из секунд в номера кадров
    exercise_ranges_frames = [
        (int(start * fps), int(end * fps), ex_type)
        for start, end, ex_type in exercise_ranges
    ]
    
    # Счетчики для упражнений
    exercise_types = ["Отжимания", "Приседания", "Подтягивания", "Планка", "Выпады"]
    exercise_stats = {ex_type: {"count": 0, "time": 0} for ex_type in exercise_types}
    current_exercise = None
    current_range_index = 0
    
    exercise_states = {
        "Отжимания": {"prev_state": "up", "counter": 0},
        "Приседания": {"prev_state": "up", "counter": 0},
        "Подтягивания": {"prev_state": "down", "counter": 0},
        "Планка": {"start_time": time.time(), "duration": 0},
        "Выпады": {"prev_state": "up", "counter": 0}
    }
    
    custom_drawing_spec = mp_drawing.DrawingSpec(
        color=DEFAULT_LANDMARK_COLOR, thickness=2, circle_radius=2)
    custom_connection_spec = mp_drawing.DrawingSpec(
        color=DEFAULT_CONNECTION_COLOR, thickness=2)
    
    with mp_pose.Pose(
        model_complexity=model_complexity,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5) as pose:
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            if current_range_index < len(exercise_ranges_frames):
                start_frame, end_frame, ex_type = exercise_ranges_frames[current_range_index]
                
                if start_frame <= processed_frames <= end_frame:
                    current_exercise = ex_type
                    exercise_stats[ex_type]["time"] += 1 / fps
                elif processed_frames > end_frame:
                    current_range_index += 1
                    current_exercise = None
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(image)
            
            if results.pose_landmarks:
                if current_exercise == "Отжимания":
                    exercise_states["Отжимания"]["counter"], exercise_states["Отжимания"]["prev_state"] = count_pushups(
                        results.pose_landmarks,
                        exercise_states["Отжимания"]["prev_state"],
                        exercise_states["Отжимания"]["counter"]
                    )
                    exercise_stats["Отжимания"]["count"] = exercise_states["Отжимания"]["counter"]
                
                elif current_exercise == "Приседания":
                    exercise_states["Приседания"]["counter"], exercise_states["Приседания"]["prev_state"] = count_squats(
                        results.pose_landmarks,
                        exercise_states["Приседания"]["prev_state"],
                        exercise_states["Приседания"]["counter"]
                    )
                    exercise_stats["Приседания"]["count"] = exercise_states["Приседания"]["counter"]
                
                elif current_exercise == "Подтягивания":
                    exercise_states["Подтягивания"]["counter"], exercise_states["Подтягивания"]["prev_state"] = count_pullups(
                        results.pose_landmarks,
                        exercise_states["Подтягивания"]["prev_state"],
                        exercise_states["Подтягивания"]["counter"]
                    )
                    exercise_stats["Подтягивания"]["count"] = exercise_states["Подтягивания"]["counter"]
                
                elif current_exercise == "Планка":
                    exercise_states["Планка"]["duration"] = count_plank(
                        results.pose_landmarks,
                        exercise_states["Планка"]["start_time"],
                        exercise_states["Планка"]["duration"]
                    )
                    exercise_stats["Планка"]["time"] = exercise_states["Планка"]["duration"]
                
                elif current_exercise == "Выпады":
                    exercise_states["Выпады"]["counter"], exercise_states["Выпады"]["prev_state"] = count_lunges(
                        results.pose_landmarks,
                        exercise_states["Выпады"]["prev_state"],
                        exercise_states["Выпады"]["counter"]
                    )
                    exercise_stats["Выпады"]["count"] = exercise_states["Выпады"]["counter"]
                
                mp_drawing.draw_landmarks(
                    image,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=custom_drawing_spec,
                    connection_drawing_spec=custom_connection_spec
                )
                
                display_text = current_exercise if current_exercise else "No exercise"
                cv2.putText(image, f"Exercise: {display_text}", (10, 30),
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            out.write(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            processed_frames += 1
    
    cap.release()
    out.release()
    
    # Читаем результат и удаляем временные файлы
    with open(output_path, 'rb') as f:
        video_data = f.read()
    
    try:
        os.remove(input_path)
        os.remove(output_path)
        os.rmdir(temp_dir)
    except Exception as e:
        print(f"Ошибка очистки: {str(e)}")
    
    # Убираем упражнения с нулевыми счетчиками
    filtered_stats = {
        ex: stats for ex, stats in exercise_stats.items()
        if stats["count"] > 0 or stats["time"] > 0
    }
    
    return jsonify({
        'processing_time': time.time() - start_time,
        'exercise_stats': filtered_stats,
        'video': video_data.decode('latin1')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)