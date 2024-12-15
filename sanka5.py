import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid

# Google Sheets API認証設定
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("test.json", scope)
    client = gspread.authorize(creds)
    return client

# スプレッドシートからイベント情報を取得
def get_event_info(key):
    client = authenticate_google_sheets()
    spreadsheet_id = '1wYtP6aaqmkmpJYnA33THaDEqHPqsge3wpBBFjfySAWk'
    sheet = client.open_by_key(spreadsheet_id).sheet1  # イベント情報が格納されているシート1を指定
    events = sheet.get_all_records()
    
    # keyに紐づいたイベント情報を抽出 (keyを文字列として比較)
    event_info = [event for event in events if str(event['key']) == str(key)]
    
    return event_info

# 参加者情報をスプレッドシートに追加
def add_participant_to_sheet(no, key, event_id, event_name, name, role, genre, dates):
    client = authenticate_google_sheets()
    spreadsheet_id = '1wYtP6aaqmkmpJYnA33THaDEqHPqsge3wpBBFjfySAWk'
    sheet = client.open_by_key(spreadsheet_id)

    # 2番目のシート（インデックスは0から始まるのでsheet2はインデックス1）を指定してアクセス
    sheet2 = sheet.get_worksheet(1)  # インデックスで指定

    # 参加者情報を追加
    sheet2.append_row([no, key, event_id, event_name, name, role, genre] + dates)

# Streamlit UI
st.title("イベント参加登録")

# イベントのkeyを入力
key = st.text_input("イベントkeyを入力してください")

if key:
    # keyに紐づいたイベント情報を取得
    event_info = get_event_info(key)
    
    if event_info:
        event = event_info[0]  # イベント情報は1つのみ抽出される想定
        event_id = event['ID']
        event_name = event['イベント名']
        event_dates = [event['日付1'], event['日付2'], event['日付3'], event['日付4'], event['日付5']]
        event_place =event["場所"]
        
        # イベント名と日付を表示
        st.write(f"イベント名: {event_name}")
        st.write(f"候補日時: {', '.join(event_dates)}")
        st.write(f"開催予定地:{event_place}周辺")
        
        # 参加者情報を入力
        name = st.text_input("参加者名")
        
        # 役職選択のプルダウン
        role = st.selectbox(
            "あなたの役職を選んでください",
            ["一般", "リーダークラス", "部長クラス", "本部長クラス", "社長クラス"],
        )
        st.write(f"選択された役職: {role}")  # デバッグ表示
        
        # ジャンル選択のプルダウン
        genre = st.selectbox("行きたいお店のジャンルを選んでください", ["和食", "中華", "イタリアン・フレンチ", "焼肉"])
        st.write(f"選択されたジャンル: {genre}")  # デバッグ表示
        
        # 日付選択（参加可能な日付を選んでもらう）
        st.write("日程ごとに以下の希望をチェックしてください:")
        options = ["絶対行ける", "たぶん行ける", "未定", "たぶん行けない", "絶対行けない"]
        
        available_dates = []
        for i, date in enumerate(event_dates, start=1):
            # ラジオボタンで表示（選択肢の番号が1〜5に対応）
            selected_option = st.radio(f"{date}の希望を選択してください", options, index=0)
            
            # 選択されたオプションをそのまま登録
            available_dates.append(selected_option)

        # 参加登録ボタン
        if st.button("参加登録"):
            if name and role:
                # Noを自動生成（参加者ごとにユニークな番号）
                no = str(uuid.uuid4())
                
                # 参加者情報をスプレッドシートに追加
                add_participant_to_sheet(no, key, event_id, event_name, name, role, genre, available_dates)
                
                st.success("参加登録が完了しました！")
            else:
                st.error("参加者名と役職を入力してください")
    else:
        st.error("指定されたkeyに該当するイベントが見つかりません")
