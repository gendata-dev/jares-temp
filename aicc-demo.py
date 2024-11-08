# gpt로 주석 작성
import openai
import csv
import os
import time
import logging
import concurrent.futures  # 추가된 모듈
from flask import Flask, request, jsonify, Response
import json

# 하드코딩 수정할 것!
openai.api_key = "sk-"

app = Flask(__name__)

CALL_LOG_FOLDER = 'call_log'
os.makedirs(CALL_LOG_FOLDER, exist_ok=True)

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# 부적절한 언어를 탐지하는 함수
def detect_inappropriate_language(user_response):
    inappropriate_keywords = [
        "씨발", "병신", "좆", "엿", "미친", "ㅅㅂ", "ㅂㅅ", "ㅈㄴ", "ㅈ같", "ㅄ",
        "ㅈ나", "개새끼", "새끼", "개년", "씹", "꺼져", "죽어", "뻑큐", "닥쳐", "꺼지",
        "엿먹어", "니애미", "니미", "느금마", "호로", "맘충", "한남", "김치녀", "틀딱",
        "빻았", "꼴통", "잡종", "빨갱이", "메갈", "한녀", "좆까", "씨부랄", "씹새끼", "퍽큐",
        "섹스", "섹", "조까", "좇같", "개좆", "씹년", "똥", "쓰레기", "바보", "망할", "변태"
    ]

    # 사용자의 응답에 부적절한 언어가 있는지 확인
    for keyword in inappropriate_keywords:
        if keyword in user_response:
            return True
    return False
1
# 모든 요청에 대한 로그 기록
@app.before_request
def log_request_info():
    logging.info(f"Request Headers: {request.headers}")
    logging.info(f"Request Body: {request.get_data()}")

# 기본 질문 생성 함수
def generate_questions():
    return {
        '오늘작목': "오늘 작업한 작물(토마토, 무화과 같은 것들)은 무엇인가요?",
        '작업': '작물에 대해 오늘 어떤 작업(모종심기, 정식 등)을 하셨나요?',
        '소요시간': '그 작업에 얼마나 시간이 걸렸나요?',
        '사용된 농기구': '오늘 사용한 농기구는 무엇인가요?',
        '사용된 농자재': '오늘 사용한 농자재는 무엇인가요?',
        '참여 인원': '작업에 참여한 사람은 몇 명인가요?',
        '인건비': '오늘 작업의 인건비는 얼마나 되나요? 만약 혼자 작업하셨으면 자가라고 이야기해주셔도 괜찮아요.',
        '평가' : '오늘 진행하신 이 전화통화에 대해서 의견 주실게 있으신가요?',
        '기타' : '혹시 궁금하시거나 하고 싶으신 이야기가 있으신가요?'
    }

# 대화 테이블이 완료되었는지 확인하는 함수
def is_table_complete(conversation_table):
    return all(value is not None for value in conversation_table.values())

# 사용자 응답에서 질문에 대한 답변을 추출하는 함수
def extract_answers(user_response, remaining_questions):
    prompt = f"""사용자의 응답: '{user_response}'\n\n다음은 남은 질문 목록입니다:\n{list(remaining_questions.values())}\n\n사용자의 응답에서 위 질문들에 대한 답변을 추출해 주세요. 각 질문에 해당하는 답변을 '질문: 답변' 형식으로 알려주세요. 만약 해당하지 않는 질문이 있다면, 그 질문은 생략하세요. 만약 작업이 없거나해서 이어지는게 없다면 넘어가세요."""
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 한국어로 질문에 대한 답변을 추출하는 AI 비서입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    extracted_info = response['choices'][0]['message']['content']
    return extracted_info

# 사용자가 질문에 대해 혼란스러워하는지 판단하는 함수
def is_user_confused(user_response):
    prompt = f"사용자의 응답: '{user_response}'\n\n사용자가 질문에 대해 추가 설명을 요구하고 있나요? '예' 또는 '아니오'로만 답변해주세요."
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 사용자 대답을 판단하는 AI 비서입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    answer = response['choices'][0]['message']['content'].strip()
    return answer == '예'

# 사용자가 질문을 건너뛰고 싶은지 판단하는 함수
def is_user_skipping_question(user_response):
    prompt = f"사용자의 응답: '{user_response}'\n\n사용자가 질문에 답변을 하지 않거나, 대답을 원하지 않거나, 모른다고 말했나요? '예' 또는 '아니오'로만 답변해주세요."
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 사용자가 답변을 원하지 않는지 판단하는 AI 비서입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    answer = response['choices'][0]['message']['content'].strip()
    return answer == '예'

# 사용자 응답에 따라 다음 질문을 생성하는 함수
def generate_followup_based_on_user_response(user_response, next_question, is_relevant, is_confused, conversation_history):
    if is_confused:
        prompt = f"""당신은 전남농업기술원 AI조사원입니다. 대화 기록은 다음과 같습니다:
{conversation_history}\n\n사용자에게 질문을 통해 답변을 받으려고해, '{next_question}'를 쉬운 표현으로 변경해서 말해 주세요."""
    elif is_relevant:
        prompt = f"""당신은 전남농업기술원 AI조사원입니다. 대화 기록은 다음과 같습니다:
{conversation_history}\n\n사용자가 '{user_response}'라고 말했습니다.\n\n앞선 대답에 맞장구 치면서, 다음 질문인 '{next_question}'을 자연스럽고 공손하게 사람처럼 말해주세요."""
    else:
        prompt = f"""당신은 전남농업기술원 AI조사원입니다. 대화 기록은 다음과 같습니다:
{conversation_history}\n\n사용자가 '{user_response}'라고 말했습니다.\n\n사용자의 말에 적절하게 응답하고, 다음 질문인 '{next_question}'으로 자연스럽게 전환해주세요."""

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 한국어로 공손하고 자연스럽게 대화하는 AI 비서입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    return response['choices'][0]['message']['content']

# 대화 테이블을 터미널에 표시하는 함수
def display_conversation_table(conversation_table):
    print("\n=== Conversation Table ===")
    for key, value in conversation_table.items():
        print(f"{key}: {value}")
    print("==========================\n")

# 대화를 CSV 파일에 저장하는 함수
def save_conversation_to_csv(call_id, summary, user_response, next_question):
    filename = f"{call_id}.csv"
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        if not file_exists:
            # CSV 헤더 설정
            writer.writerow(["call_id", "Summary", "User Response", "Next Question"])

        # 대화 내용 추가
        writer.writerow([call_id, summary, user_response, next_question])

# TTS 응답을 스트리밍하는 함수
def stream_tts_response(tts_text):
    for char in tts_text:
        yield json.dumps({"content": {"tts": char}}) + '\n'

# 각 call_id에 대해 대화 상태를 저장하는 딕셔너리
conversations = {}

# 답변 요청을 처리하는 함수 (통화 시작 시 호출)
@app.route('/v1/answer', methods=['POST'])
def handle_answer():
    data = request.json
    call_id = data.get('call_id')
    answer_time = data.get('answer_time')
    direction = data.get('direction')

    logging.info(f"Answer received. Call ID: {call_id}, Answer Time: {answer_time}, Direction: {direction}")

    return jsonify({"response_message": {"code": "0000", "message": "성공"}}), 200

# 다음 질문을 선택하는 함수
def select_next_question(remaining_questions):
    for key, question in remaining_questions.items():
        return question, key
    return "모든 질문이 완료되었습니다. 통화를 종료합니다.", None

# 대화 요청을 처리하는 함수
@app.route('/v1/talk', methods=['POST'])
def handle_talk():
    data = request.json
    call_id = data.get('call_id')
    stt = data.get('stt') or "No speech detected"

    # 대화 초기화
    if call_id not in conversations:
        conversations[call_id] = {
            'conversation_table': {
                '오늘작목': None,
                '작업': None,
                '소요시간': None,
                '사용된 농기구': None,
                '사용된 농자재': None,
                '참여 인원': None,
                '인건비': None,
                '평가' : None,
                '기타': None
            },
            'remaining_questions': generate_questions(),
            'prev_summary': "",
            'first_greeting_done': False,
            'conversation_history': []
        }

    conv = conversations[call_id]

    # 첫 인사
    if not conv['first_greeting_done']:
        conv['first_greeting_done'] = True
        next_question, asked_question_key = select_next_question(conv['remaining_questions'])
        conv['asked_question_key'] = asked_question_key
        greeting = f"안녕하세요 전남농기원 AI 조사원입니다 농업조사를 위해 연락드렸습니다 {next_question}"
        print(f"Greeting: {greeting}")
 
        def generate_greeting_response():
            response_message = {
                "response_message": {
                    "code": "0000",
                    "message": "성공",
                    "tts_speed": 1,
                    "barge_in": False,
                    "next_action": "10",
                    "epd": 1200,
                    "dtmf_min": 5,
                    "dtmf_max": 5,
                    "dtmf_timeout": 5,
                    "transfer_number": "01049136887",
                    "hangup_delay": 3,
                    "tts_speaker": "vdonghyun"
                }
            }

            
            yield json.dumps(response_message) + '\n'
            for chunk in stream_tts_response(greeting):
                yield chunk

        return Response(generate_greeting_response(), mimetype='application/json')

    # 부적절한 언어 탐지
    if detect_inappropriate_language(stt):
        inappropriate_response = "오류가 발생했습니다."

        def generate_response():
            response_message = {
                "response_message": {
                    "code": "0000",
                    "message": "성공",
                    "tts_speed": -1,
                    "barge_in": False,
                    "next_action": "90",
                    "epd": 1000,
                    "dtmf_min": 5,
                    "dtmf_max": 5,
                    "dtmf_timeout": 5,
                    "transfer_number": "01049136887",
                    "hangup_delay": 3
                }
            }

            yield json.dumps(response_message) + '\n'
            for chunk in stream_tts_response(inappropriate_response):
                yield chunk

        return Response(generate_response(), mimetype='application/json')

    # 대화 기록 업데이트
    conv['conversation_history'].append(f"사용자: {stt}")

    # 스레드 풀을 사용해 API 호출 병렬 처리
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_extract_answers = executor.submit(extract_answers, stt, conv['remaining_questions'])
        future_is_confused = executor.submit(is_user_confused, stt)
        future_is_skipping_question = executor.submit(is_user_skipping_question, stt)

        extracted_info_raw = future_extract_answers.result()
        is_confused = future_is_confused.result()
        is_skipping = future_is_skipping_question.result()

    # 추출된 정보를 파싱하여 대화 테이블에 업데이트
    extracted_info = {}
    lines = extracted_info_raw.strip().split('\n')
    for line in lines:
        if '질문:' in line and '답변:' in line:
            parts = line.split('질문:', 1)[1].split('답변:')
            if len(parts) == 2:
                question = parts[0].strip()
                answer = parts[1].strip()
                extracted_info[question] = answer

    answers_found = False
    for question_text, answer in extracted_info.items():
        key = None
        for k, q in conv['remaining_questions'].items():
            if q == question_text:
                key = k
                break
        if key:
            conv['conversation_table'][key] = answer
            conv['remaining_questions'].pop(key)
            conv['conversation_history'].append(f"AI: {question_text} -> 답변: {answer}")
            answers_found = True

    # 질문 건너뛰기 처리
    if not answers_found:
        if is_skipping:
            current_question_key = conv['asked_question_key']
            conv['conversation_table'][current_question_key] = ''
            conv['remaining_questions'].pop(current_question_key)
            conv['conversation_history'].append(f"AI: {current_question_key} 질문을 건너뜀")
            answers_found = True

    # 모든 질문 완료 여부 확인
    if is_table_complete(conv['conversation_table']):
        closing_message = "모든 질문이 완료되었습니다 통화를 종료합니다."
        display_conversation_table(conv['conversation_table'])
        conv['prev_summary'] += f" '님께서' '{stt}'라고 말씀하셨습니다."
        save_conversation_to_csv(call_id, conv['prev_summary'], stt, closing_message)

        def generate_response():
            response_message = {
                "response_message": {
                    "code": "0000",
                    "message": "성공",
                    "tts_speed": -1,
                    "barge_in": False,
                    "next_action": "90",
                    "epd": 1000,
                    "dtmf_min": 5,
                    "dtmf_max": 5,
                    "dtmf_timeout": 5,
                    "transfer_number": "01049136887",
                    "hangup_delay": 3
                }
            }
            yield json.dumps(response_message) + '\n'
            for chunk in stream_tts_response(closing_message):
                yield chunk

        return Response(generate_response(), mimetype='application/json')

    # 다음 질문 선택
    next_question, asked_question_key = select_next_question(conv['remaining_questions'])
    conv['asked_question_key'] = asked_question_key
    is_relevant = answers_found
    conversation_history = '\n'.join(conv['conversation_history'])
    rephrased_question = generate_followup_based_on_user_response(stt, next_question, is_relevant, is_confused, conversation_history)
    conv['prev_summary'] += f" '님께서' '{stt}'라고 말씀하셨습니다."
    conv['conversation_history'].append(f"AI: {rephrased_question}")
    save_conversation_to_csv(call_id, conv['prev_summary'], stt, rephrased_question)

    def generate_response():
        response_message = {
            "response_message": {
                "code": "0000",
                "message": "성공",
                "tts_speed": -1,
                "barge_in": False,
                "next_action": "10",
                "epd": 1000,
                "dtmf_min": 5,
                "dtmf_max": 5,
                "dtmf_timeout": 5,
                "transfer_number": "01049136887",
                "hangup_delay": 3
            }
        }
        yield json.dumps(response_message) + '\n'
        for chunk in stream_tts_response(rephrased_question):
            yield chunk

    return Response(generate_response(), mimetype='application/json')

# 통화 종료 요청을 처리하는 함수
@app.route('/v1/hangup', methods=['POST'])
def handle_hangup():
    call_data = extract_call_data(request.json)
    store_csv_file(call_data)

    call_id = call_data.get('call_id')
    logging.info(f"Hangup received. Call ID: {call_id}, Duration: {call_data.get('duration')}")

    if call_id in conversations:
        del conversations[call_id]

    """
    Response
    code	string	처리 결과 코드		0000
    message	string	메시지		success
    """
    return jsonify({"status": "success", "message": "Hangup request processed"}), 200

def extract_call_data(data):
    return {
        'call_id': data.get('call_id'),
        't_id': data.get('t_id'),
        'caller': data.get('caller'),
        'callee': data.get('callee'),
        'start_time': data.get('start_time'),
        'answer_time': data.get('answer_time'),
        'end_time': data.get('end_time'),
        'duration': data.get('duration'),
        'dial_duration': data.get('dial_duration'),
        'hangup_disposition': data.get('hangup_disposition')
    }

def store_csv_file(call_data):
    """
    csv 파일을 저장하는 함수
    프로젝트의 경로에 /call_log 디렉토리에
    <call_id>.csv 파일을 생성함

    call_id는 unique한 uuid4 값
    같은 이름의 파일이 생기지 않음
    
    드물게 같은 이름의 파일이 생길 경우
    값을 덮어씌운다
    """
    file_path = os.path.join(CALL_LOG_FOLDER, f"{call_data['call_id']}.csv")

    if not os.path.exists(CALL_LOG_FOLDER):
        logging.error(f"Directory was deleted {CALL_LOG_FOLDER}")
        os.makedirs(CALL_LOG_FOLDER)

    try:
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            headers = call_data.keys()
            writer.writerow(headers)
            writer.writerow(call_data.values())

    except PermissionError:
        logging.error(f"Permission denied {file_path}")
        return jsonify({
            "error": "Permission denied: Unable to write to the file at the specified path."
        }),403
    except FileNotFoundError:
        logging.error(f"File not found {file_path}")
        return jsonify({
            "error": "File path not found or the directory does not exist."
        }), 404
    except OSError as e:
        logging.error(f"OSError {file_path}")
        return jsonify({
            "error": f"An unexpected error occurred: {e.strerror}"
        }), 500
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12123, debug=True)