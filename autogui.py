import requests
import pandas as pd
import time
from datetime import datetime

# 통화 시작, 응답, 대화, 통화 종료를 위한 API URL 정의
DIAL_API_URL = 'http://110.165.19.34:8000/v1/call/dial'  # 통화를 시작하는 API URL
ANSWER_API_URL = 'http://aicc_test.gendata.me/v1/answer'
TALK_API_URL = 'http://aicc_test.gendata.me/v1/talk'
HANGUP_API_URL = 'http://aicc_test.gendata.me/v1/hangup'

# 통화를 시작하는 함수 (Dial API 호출)
def initiate_call(t_id, caller, callee):
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': 'rvCbjRSAPYc74TC96Ayok7qK9hMFsb9eOtjXI7bh8eQ'  # API 키
    }

    call_data = {
        "t_id": t_id if t_id else None,  
        "caller": caller,
        "callee": callee,
        "dial_timeout": 50  # 통화 시도 시간 (초)
    }

    try:
        # API 요청을 보내고 응답 처리
        response = requests.post(DIAL_API_URL, headers=headers, json=call_data)
        if response.status_code == 200:
            response_data = response.json()
            call_id = response_data.get('call_id')  # 호출 ID 반환
            return call_id
        else:
            print(f"{callee}에 대한 통화 시작 실패. 상태 코드: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"{callee}에 대한 요청 오류: {e}")
        return None

# CSV 파일 로드
#file_path = 'listup4913_1003_24_39.csv' # yj수정: listup4913_1003.csv -> listup4913_1003_24_39.csv
file_path = 'listup4913_1003_1_23.csv' # yj수정: listup4913_1003.csv -> listup4913_1003_1_23.csv

df = pd.read_csv(file_path, dtype={'연락처': str})  # CSV 파일을 읽어 전화번호 목록 로드

# 'Call ID' 열이 없으면 추가
if 'call_id' not in df.columns:
    df['call_id'] = None

# 고정된 T ID 및 발신자 번호
t_id_input = "1234567890"  # 고정된 T ID
caller_input = "07079190360"  # 고정된 발신자 번호

# CSV 파일에서 수신자 전화번호 목록 추출
phone_numbers = df['연락처'].tolist()

# 5개의 전화번호씩 3분 간격으로 처리
batch_size = 5
delay_seconds = 180  # 3분

# 전화번호 목록을 배치 단위로 반복
for start_idx in range(0, len(phone_numbers), batch_size):
    batch = phone_numbers[start_idx:start_idx + batch_size]

    # 현재 배치의 각 전화번호 처리
    for idx, callee_input in enumerate(batch, start=start_idx):
        call_id = initiate_call(t_id_input, caller_input, callee_input)
        if call_id:
            print(f"{callee_input}에 대한 통화가 성공적으로 시작되었습니다! Call ID: {call_id}")
            df.at[idx, 'call_id'] = call_id  # 해당 행의 'call_id' 열 업데이트
        else:
            print(f"{callee_input}에 대한 통화 시작 실패.")

    # 각 배치가 끝난 후 Call ID를 업데이트한 CSV 저장
    df.to_csv(file_path, index=False)
    print(f"배치 {start_idx // batch_size + 1} 처리 후 CSV가 업데이트되었습니다.")

    # 다음 배치 처리 전 3분 대기
    if start_idx + batch_size < len(phone_numbers):
        print("다음 배치를 처리하기 위해 3분 대기 중...")
        time.sleep(delay_seconds)

print("모든 배치 처리가 완료되었습니다.")
