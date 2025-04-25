import streamlit as st
import tempfile
import os
import requests
import pandas as pd
import cv2
from typing import Dict 

# Настройки Streamlit
st.set_page_config(
    page_title="Онлайн Физкульутра",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Глобальные переменные
if 'exercise_ranges' not in st.session_state:
    st.session_state.exercise_ranges = []
    
exercise_types = ["Отжимания", "Приседания", "Подтягивания", "Планка", "Выпады"]

def calculate_workout_score(plan_name: str, stats_df: pd.DataFrame) -> Dict:
    """Рассчитывает процент выполнения и оценку тренировки"""
    plan_stats = {
        "Новичок – 1 круг": {
            "Отжимания": 10,
            "Приседания": 20,
            "Планка": 30 
        },
        "Классика – 2 круга": {
            "Отжимания": 15,
            "Приседания": 30,
            "Подтягивания": 10,
            "Планка": 45
        },
        "Полная тренировка": {
            "Отжимания": 20,
            "Приседания": 30,
            "Подтягивания": 15,
            "Планка": 60,
            "Выпады": 20
        },
        "Силовая": {
            "Отжимания": 30,
            "Подтягивания": 20,
            "Планка": 90
        },
        "Ноги и корпус": {
            "Приседания": 40,
            "Выпады": 30,
            "Планка": 60
        }
    }
    
    if plan_name not in plan_stats:
        return {"error": "Unknown plan"}
    
    results = {}
    total_percent = 0
    exercise_count = 0
    
    for exercise, target in plan_stats[plan_name].items():
        # Для планки учитываем время, для остальных - количество
        if exercise == "Планка":
            actual = stats_df.loc[exercise, "Время (сек)"] if exercise in stats_df.index else 0
        else:
            actual = stats_df.loc[exercise, "Количество"] if exercise in stats_df.index else 0
        
        percent = min(100, round((actual / target) * 100)) if target > 0 else 0
        results[exercise] = {
            "target": target,
            "actual": actual,
            "percent": percent
        }
        total_percent += percent
        exercise_count += 1
    
    if exercise_count > 0:
        overall_percent = total_percent / exercise_count
        # Оценка от 1 до 5
        if overall_percent >= 90:
            grade = "5 (Отлично)"
        elif overall_percent >= 70:
            grade = "4 (Хорошо)"
        elif overall_percent >= 50:
            grade = "3 (Удовлетворительно)"
        elif overall_percent >= 30:
            grade = "2 (Плохо)"
        else:
            grade = "1 (Очень плохо)"
    else:
        overall_percent = 0
        grade = "Нет данных"
    
    return {
        "exercises": results,
        "overall_percent": overall_percent,
        "grade": grade
    }

def show_workout_summary(plan_name: str, stats_df: pd.DataFrame):
    """Показывает сводку выполнения плана тренировки"""
    st.subheader("📝 Сводка выполнения плана")
    
    summary = calculate_workout_score(plan_name, stats_df)
    
    if "error" in summary:
        st.error(summary["error"])
        return
    
    # Создаем DataFrame для отображения
    summary_data = []
    for ex, data in summary["exercises"].items():
        summary_data.append({
            "Упражнение": ex,
            "План": data["target"],
            "Выполнено": data["actual"],
            "Процент": f"{data['percent']}%",
            "Индикатор": data["percent"]
        })
    
    df_summary = pd.DataFrame(summary_data)
    
    # Отображаем таблицу
    st.dataframe(df_summary)
    
    # Прогресс-бар для общего выполнения
    st.metric("Общий процент выполнения", f"{summary['overall_percent']:.0f}%")
    st.progress(summary['overall_percent'] / 100)
    
    # Оценка
    st.markdown(f"### Оценка тренировки: {summary['grade']}")
    
    # Рекомендации
    if summary['overall_percent'] >= 90:
        st.success("🎉 Отличный результат! Вы полностью выполнили план тренировки!")
    elif summary['overall_percent'] >= 70:
        st.info("👍 Хорошая тренировка! Почти достигли идеального результата!")
    elif summary['overall_percent'] >= 50:
        st.warning("👌 Неплохо, но есть куда расти! Попробуйте сделать больше повторений в следующий раз.")
    else:
        st.error("💪 Слишком мало! Вам нужно серьезнее подойти к тренировке!")

def extract_exercise_ranges(video_path: str) -> list:
    """Форма для ввода временных отрезков для каждого упражнения"""
    st.subheader("📝 Разметка упражнений")
    
    # Получаем длительность видео
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    cap.release()
    
    st.info(f"Длительность видео: {duration:.2f} сек ({total_frames} кадров)")
    
    st.markdown("### Задайте интервалы для упражнений")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        exercise_type = st.selectbox("Тип упражнения", exercise_types, key="ex_type_input")
    with col2:
        start_sec = st.number_input("Время начала (сек)", min_value=0.0, max_value=float(duration), value=0.0, step=0.1, key="start_sec")
    with col3:
        end_sec = st.number_input("Время конца (сек)", min_value=0.0, max_value=float(duration), value=5.0, step=0.1, key="end_sec")
    with col4:
        if st.button("Добавить интервал"):
            if start_sec < end_sec:
                st.session_state.exercise_ranges.append((start_sec, end_sec, exercise_type))
                st.success(f"Интервал для {exercise_type}: {start_sec:.2f} сек - {end_sec:.2f} сек добавлен")
            else:
                st.error("Время начала должно быть меньше времени конца")
    
    st.subheader("📋 Текущая разметка")
    if st.session_state.exercise_ranges:
        df_ranges = pd.DataFrame(
            st.session_state.exercise_ranges,
            columns=["Начало (сек)", "Конец (сек)", "Тип упражнения"]
        )
        df_ranges["Длительность (сек)"] = df_ranges["Конец (сек)"] - df_ranges["Начало (сек)"]
        st.dataframe(df_ranges)
        if st.button("❌ Очистить разметку"):
            st.session_state.exercise_ranges = []
            st.rerun()
    else:
        st.info("Интервалы для упражнений еще не заданы")
    
    return st.session_state.exercise_ranges

def show_results(result: dict, plan_name: str):
    """Отображение результатов анализа"""
    st.success(f"✅ Анализ завершен за {result['processing_time']:.2f} сек")
    st.markdown("---")
    
    st.subheader("📊 Результаты анализа")
    filtered_stats = {
        ex: stats for ex, stats in result['exercise_stats'].items()
        if stats["count"] > 0 or stats["time"] > 0
    }

    if filtered_stats:
        stats_df = pd.DataFrame.from_dict(filtered_stats, orient='index')
        stats_df.columns = ["Количество", "Время (сек)"]
        st.dataframe(stats_df)
        
        # Показываем сводку по плану тренировки
        show_workout_summary(plan_name, stats_df)
        
        # Графики
        st.subheader("📈 Графики")
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(stats_df["Количество"])
            st.caption("Количество повторов")
        with col2:
            st.bar_chart(stats_df["Время (сек)"])
            st.caption("Время выполнения (сек)")
    else:
        st.warning("⛔ Упражнения не были распознаны или не выполнены.")

# Интерфейс приложения
st.title("🏋️ Физкультура онлайн")

# Программы тренировок
st.subheader("🧩 Выберите план тренировки")

plans = {
    "Новичок – 1 круг": [
        "10 отжиманий",
        "20 приседаний",
        "30 секунд планки"
    ],
    "Классика – 2 круга": [
        "15 отжиманий",
        "30 приседаний",
        "10 подтягиваний",
        "45 секунд планки"
    ],
    "Полная тренировка": [
        "20 отжиманий",
        "30 приседаний",
        "15 подтягиваний",
        "60 секунд планки",
        "20 выпадов"
    ],
    "Силовая": [
        "30 отжиманий",
        "20 подтягиваний",
        "90 секунд планки"
    ],
    "Ноги и корпус": [
        "40 приседаний",
        "30 выпадов",
        "60 секунд планки"
    ]
}

plan_name = st.selectbox("План тренировки", list(plans.keys()), index=0)

st.markdown("**Программа тренировки:**")
for i, step in enumerate(plans[plan_name], 1):
    st.markdown(f"{i}. {step}")

st.markdown("""
    ### Инструкция:
    1. Загрузите видео тренировки.
    2. Задайте интервалы (в секундах) для каждого упражнения.
    3. Запустите анализ.
    4. Получите статистику по каждому упражнению.
""")
st.markdown("---")

uploaded_file = st.file_uploader(
    "📤 ЗАГРУЗИТЕ ВИДЕО ТРЕНИРОВКИ",
    type=["mp4", "avi", "mov"],
    help="Поддерживаемые форматы: MP4, AVI, MOV"
)

if uploaded_file:
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.mp4")
    
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.subheader("🎬 Предпросмотр видео")
    st.video(input_path)

    exercise_ranges = extract_exercise_ranges(input_path)
    
    if exercise_ranges and st.button("🚀 НАЧАТЬ АНАЛИЗ УПРАЖНЕНИЙ", use_container_width=True):
        with st.spinner("⏳ Анализ упражнений..."):
            try:
                with open(input_path, 'rb') as f:
                    files = {'video': f}
                    data = {
                        'exercise_ranges': str(exercise_ranges),
                        'model_complexity': 1
                    }
                    response = requests.post('http://localhost:5000/process_video', files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    show_results(result, plan_name)
                    
                    # Кнопка скачивания результатов
                    csv = pd.DataFrame.from_dict(result['exercise_stats'], orient='index').to_csv(index=True).encode('utf-8')
                    st.download_button(
                        label="📊 СКАЧАТЬ СТАТИСТИКУ",
                        data=csv,
                        file_name="workout_stats.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.error(f"Ошибка API: {response.text}")
            except Exception as e:
                st.error(f"Ошибка соединения с API: {str(e)}")
        
        try:
            os.remove(input_path)
            os.rmdir(temp_dir)
        except Exception as e:
            st.error(f"🚨 Ошибка очистки: {str(e)}")

st.markdown("---")
st.markdown("🛠️ Created with Streamlit & Flask API | Физкультура Онлайн")