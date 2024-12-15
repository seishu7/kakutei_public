import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
from datetime import datetime
import pandas as pd
import numpy as np
import requests
import folium
from streamlit_folium import folium_static
from dotenv import load_dotenv
import os

# Google Sheets API認証設定
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("test.json", scope)
    client = gspread.authorize(creds)
    return client

# スプレッドシートにデータを追加する関数
def add_event_to_sheet(event_name, event_id, key, place, event_dates):
    # スプレッドシートを開く
    client = authenticate_google_sheets()
    spreadsheet_id = '1wYtP6aaqmkmpJYnA33THaDEqHPqsge3wpBBFjfySAWk'
    sheet = client.open_by_key(spreadsheet_id).sheet1

    # データを横並びに追加（ID、イベント名、key、日付1～日付5）
    sheet.append_row([event_id, event_name, str(key), place] + event_dates)  # keyを文字列として保存

# Streamlitのセッション状態を初期化
if "show_ad_email_button" not in st.session_state:
    st.session_state["show_ad_email_button"] = False  # メール作成ボタンの状態

# ストリームリットUI
st.sidebar.title("イベント登録フォーム")

# イベント名入力
event_name = st.sidebar.text_input("イベント名")

# key入力
key = st.sidebar.text_input("key(アルファベットで記入してください)")

#開催地入力
place = st.sidebar.text_input("開催地を記入してください")

# 日付入力（カレンダーで複数日付）
event_dates = []
for i in range(5):
    date = st.sidebar.date_input(f"日付 {i+1}")
    event_dates.append(str(date))

# IDを自動生成（UUID）
event_id = str(uuid.uuid4())

# 送信ボタン
if st.sidebar.button("登録"):
    if event_name and key:
        add_event_to_sheet(event_name, event_id, key, place, event_dates)
        st.sidebar.success("イベントが登録されました！")
    else:
        st.sidebar.error("イベント名とkeyは必須です。")
    
# 「メール文を作成」ボタンの処理
if st.sidebar.button("日程調整メール文を作成"):
    st.session_state["show_ad_email_button"] = True  # メール文作成ボタンが押された状態を記録

# メール文作成エリア
if st.session_state["show_ad_email_button"]:
    st.markdown("### 案内メール定型文")
    default_email = (
        f"件名: 【ご協力お願いします】飲み会日程調整のご案内\n\n"
        f"皆様\n\n"
        f"お世話になっております。\n"
        f"この度、飲み会を企画しております。\n"
        f"つきましては、皆様のご都合を確認させていただきたく、日程調整にご協力をお願いいたします。\n\n"
        f"以下のリンクより、ご都合の良い日程を入力してください。\n\n"
        f"【日程調整リンク】\n"
        f"<リンクをここに挿入>\n\n"
        f"お忙しいところ恐れ入りますが、〇月〇日（締切日）までにご回答をお願いいたします。\n"
        f"皆様のご参加を心よりお待ちしております！\n\n"
        f"どうぞよろしくお願いいたします。\n\n"
        f"幹事より"
    )
    email_text = st.text_area("案内メール文を編集してください", value=default_email, height=200)
    
    # 「メール定型文をコピー」ボタン
    if st.button("メール定型文をコピー"):
        st.write("メール定型文をコピーしました！")    

#最適日程の算出
st.title("🎉 飲み会日程調整アプリ 🍻")
st.write("参加者の日程登録が完了したら、下記ボタンで最適日程を出してください！")

# スプレッドシートから幹事情報を取得
def get_responses(key):
    client = authenticate_google_sheets()
    spreadsheet_id = '1wYtP6aaqmkmpJYnA33THaDEqHPqsge3wpBBFjfySAWk'
    sheet = client.open_by_key(spreadsheet_id)
    sheet2 = sheet.get_worksheet(1)  # 参加者情報が格納されているシート2を指定
    data = sheet2.get_all_records()

    # keyに紐づいた参加者情報を抽出
    filtered_data = [row for row in data if str(row['key']) == str(key)]

    # pandas DataFrameに変換
    df = pd.DataFrame(filtered_data)

    return df

# スプレッドシートから日程情報を取得
def get_dates_by_key(key):
    client = authenticate_google_sheets()
    spreadsheet_id = '1wYtP6aaqmkmpJYnA33THaDEqHPqsge3wpBBFjfySAWk'
    sheet = client.open_by_key(spreadsheet_id)
    sheet1 = sheet.get_worksheet(0)  # 日程情報が格納されているシート1を指定
    data = sheet1.get_all_records()

    # keyに紐づいた日程情報を抽出
    filtered_data = [row for row in data if str(row['key']) == str(key)]

    # デバッグ: フィルタリングされたデータの表示
    #st.write(f"フィルタリングされたデータ: {filtered_data}")

    if filtered_data:
        # すべての"日付"列を取り出し、それらを日程マッピングに追加
        dates_mapping = {}
        for i in range(1, 6):  # 日付1〜日付5を想定
            date_column = f"日付{i}"
            if date_column in filtered_data[0]:  # もしその列が存在する場合
                dates_mapping[date_column] = filtered_data[0][date_column]
        
        # デバッグ: 日程マッピングの内容を表示
        #st.write(f"日程マッピング: {dates_mapping}")

        return dates_mapping
    return {}
    
# スコア計算の関数
def calculate_scores(responses, date_mapping, weights):
    scores = {date_mapping[day]: 0 for day in date_mapping}  # ISO日付に基づいた初期化
    genre_scores = {date_mapping[day]: {} for day in date_mapping}

    # 各参加者のレスポンスをもとにスコア計算
    for _, response in responses.iterrows():
        role_weight = weights.get(response["役職"], 1)  # 役職に基づいた重み付け
        selected_genre = response.get("genre", "")  # ジャンル

        for day, iso_date in date_mapping.items():  # 日付1 → ISO日付のマッピングで処理
            if day in response:  # `日付1`, `日付2` などが存在する場合
                choice = response[day]
                if choice == "絶対行ける":
                    scores[iso_date] += 2 * role_weight
                elif choice == "たぶん行ける":
                    scores[iso_date] += 1 * role_weight

                # ジャンルのスコアを更新
                if selected_genre not in genre_scores[iso_date]:
                    genre_scores[iso_date][selected_genre] = 0
                if choice in ["絶対行ける", "たぶん行ける"]:
                    genre_scores[iso_date][selected_genre] += role_weight

    return scores, genre_scores

# Streamlit UI

# セッション状態の初期化
if "show_key_input" not in st.session_state:
    st.session_state["show_key_input"] = False
if "key" not in st.session_state:
    st.session_state["key"] = ""
if "button_clicked" not in st.session_state:
    st.session_state["button_clicked"] = False
if "rmax" not in st.session_state:
    st.session_state.rmax = 1000
if "df_info" not in st.session_state:
    st.session_state.df_info = pd.DataFrame()
if "balloons_shown" not in st.session_state:
    st.session_state["balloons_shown"] = False  # バルーンの状態を初期化
if "show_email_button" not in st.session_state:
    st.session_state["show_email_button"] = False  # メール作成ボタンの状態

# ボタンを作成
# ステップ1: 最適日程とジャンルの計算
if st.button("最適日程とジャンル計算"):
    st.session_state["show_key_input"] = True

if st.session_state["show_key_input"]:
    st.write("計算に必要なイベントKeyを入力してください")
    key = st.text_input("イベントkeyを入力してください", value=st.session_state["key"])
    st.session_state["key"] = key

    if key:
        responses = get_responses(key)
        date_mapping = get_dates_by_key(key)

        if not responses.empty and date_mapping:


            # 役職ごとの重み
            weights = {
                "社長クラス": 5,
                "本部長クラス": 4,
                "部長クラス": 3,
                "リーダークラス": 2,
                "一般": 1,
            }

            # スコア計算
            scores, genre_scores = calculate_scores(responses, date_mapping, weights)

            # 最適日程とジャンルの表示
            best_date = max(scores, key=scores.get)
            best_date_score = scores[best_date]  # 最適日程のスコア

            best_genre = max(genre_scores[best_date], key=genre_scores[best_date].get)
            best_genre_score = genre_scores[best_date][best_genre]  # 最適ジャンルのスコア

            # 表示
            st.markdown(f"<h2 style='color: red;'>🎉 最適な飲み会の日程が確定しました！ </h2>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color: green;'>🌟 最適日程: {best_date} 🌟</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: blue;'>スコア: {best_date_score} 点</p>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color: green;'>🌟 ジャンル: {best_genre} 🌟</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: blue;'>スコア: {best_genre_score} 点</p>", unsafe_allow_html=True)

             # 詳細スコア結果確認したい時に確認してください。
            #st.markdown("<h3>\u30b9\u30b3\u30a2\u306e\u8a73\u7d30\u7d50\u679c</h3>", unsafe_allow_html=True)
            #scores_df = pd.DataFrame(scores.items(), columns=["日程", "スコア"])
            #st.write(scores_df)

            #st.markdown("<h3>ジャンルごとのスコア</h3>", unsafe_allow_html=True)
            #genre_scores_df = pd.DataFrame.from_dict(genre_scores, orient="index").fillna(0)
            #st.write(genre_scores_df)

            # バルーンを一度だけ表示
            if not st.session_state["balloons_shown"]:
                st.balloons()
                st.session_state["balloons_shown"] = True  # バルーンを表示したことを記録

            # ボタンでお店リスト作成に移動
            if st.button("お店リスト作成に移る"):
                st.session_state.button_clicked = True
        else:
            st.error("指定されたkeyに基づくデータが見つかりません")

# ステップ2: お店リスト作成
if st.session_state.button_clicked:
    st.markdown("## お店リスト作成")
    def get_event_info(key):
        client = authenticate_google_sheets()
        spreadsheet_id = '1wYtP6aaqmkmpJYnA33THaDEqHPqsge3wpBBFjfySAWk'
        sheet = client.open_by_key(spreadsheet_id).sheet1  # イベント情報が格納されているシート1を指定
        events = sheet.get_all_records()
    
        # keyに紐づいたイベント情報を抽出 (keyを文字列として比較)
        event_info = [event for event in events if str(event['key']) == str(key)]
    
        return event_info
    event_info = get_event_info(st.session_state["key"])
    if event_info:
        event_place = event_info[0]["場所"]
        st.write(f"イベント場所: {event_place}")

        # 地点情報の取得
        load_dotenv()
        API_KEY_G = os.getenv("API_KEY_G")
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={event_place}&language=ja&region=jp&key={API_KEY_G}"
        response = requests.get(url)
        results = response.json().get("results", [])

        if not results:
            st.error("住所に該当する結果が見つかりませんでした。")
            st.stop()

        lat = results[0]["geometry"]["location"]["lat"]
        lng = results[0]["geometry"]["location"]["lng"]

        # 範囲と施設の種類を選択
        st.markdown("### 検索範囲とジャンル")
        rmax = st.number_input(
            "検索範囲 (最大5000m)", min_value=0, max_value=5000, value=st.session_state.rmax, step=500
        )
        st.session_state.rmax = rmax
        facility_type = {"飲食店": "restaurant"}
        typ=facility_type
        kyw = best_genre

        # Google Places API 呼び出し
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&language=ja&radius={rmax}&type={typ}&keyword={kyw}&key={API_KEY_G}"
        response = requests.get(url)
        results = response.json().get("results", [])

        # 店舗URLを取得する関数
        def get_place_url(place_id, api_key):           
            url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=url,website&key={api_key}"
            response = requests.get(url)
            
            # レスポンスが成功した場合
            if response.status_code == 200:
                result = response.json().get("result", {})
                # URLフィールドを取得する
                google_maps_url = result.get("url")
                if not google_maps_url:  # urlがない場合、websiteを使う
                    google_maps_url = result.get("website")
                
                return google_maps_url
            else:
                print(f"Error fetching details for place_id: {place_id}, status code: {response.status_code}")
                return None
        # 価格レベルを文字列に変換する関数
        def map_price_level(price_level):
            price_mapping = {
                0: "無料",
                1: "安価",
                2: "普通",
                3: "高価",
                4: "とても高価",
            }
            return price_mapping.get(price_level, "不明")

        # 結果を施設情報としてリストに追加
        facilities_info = []
        for result in results:
            place_id = result.get("place_id")
            google_maps_url = None
            if place_id:
                google_maps_url = get_place_url(place_id, API_KEY_G)  # URLを取得
                
                
            facilities_info.append({
                "ID": result["place_id"],
                "名前": result["name"],
                "評価": result.get("rating"),
                "口コミ数": result.get("user_ratings_total"),
                "価格": map_price_level(result.get("price_level")),  # 数値から文字列に変換
                "営業中": result.get("opening_hours", {}).get("open_now"),
                "緯度": result["geometry"]["location"].get("lat"),
                "経度": result["geometry"]["location"].get("lng"),
                "Google Maps URL": google_maps_url  # Google Maps URLを設定
            })

        st.session_state.df_info = pd.DataFrame(facilities_info)

        # ソート機能
        st.markdown("### ソートオプション")
        sort_by = st.selectbox(
            "どの項目でソートしますか？",
            options=["名前", "評価", "口コミ数", "価格"],
            index=1
        )

        sort_order = st.radio(
            "ソート順を選択してください",
            options=["昇順", "降順"],
            index=1
        )

        # ソート処理
        ascending = sort_order == "昇順"
        if not st.session_state.df_info.empty:
            sorted_df = st.session_state.df_info.sort_values(
                by=sort_by, ascending=ascending, na_position="last"
            ).reset_index(drop=True)

            # ソート後の結果を表示
            st.markdown("### ソート後の結果")
            st.dataframe(sorted_df)
        else:
            st.warning("検索結果がまだありません。")

        # 地図表示
        st.markdown("### 地図表示")
        m = folium.Map(location=[lat, lng], zoom_start=15)

        # 中心地をマーカーで表示
        folium.Marker(
            location=[lat, lng], 
            popup="中心地", 
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

        # 検索範囲を表示
        folium.Circle(
            radius=rmax, 
            location=[lat, lng], 
            color="blue", 
            fill=True, 
            fill_opacity=0.1
        ).add_to(m)

        # 各店舗を地図上に追加
        for _, row in sorted_df.iterrows():
            # 各店舗のGoogle Mapsリンク付きポップアップを作成
            popup_html = f'<a href="{row["Google Maps URL"]}" target="_blank">{row["名前"]}</a>'
            popup = folium.Popup(popup_html, max_width=300)
            
            # マーカーを地図に追加
            folium.Marker(
                location=[row["緯度"], row["経度"]], 
                popup=popup, 
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)

        # Streamlitに地図を表示
        folium_static(m)

        # 「メール文を作成」ボタンの処理
        if st.sidebar.button("メール文を作成"):
            st.session_state["show_email_button"] = True  # メール文作成ボタンが押された状態を記録

        # 案内メールの定型文生成
        st.markdown("### 案内メール定型文")
        default_email = (
            f"件名: 【確定】飲み会日程のお知らせ\n\n"
            f"皆様\n\n"
            f"お忙しい中、飲み会日程調整にご協力いただきありがとうございました。\n"
            f"AIによるスコア計算の結果、以下の日程に決定いたしました！\n\n"
            f"【最適日程】\n"
            f" {best_date} \n\n"
            f"【お店】"
            f"店名：確定次第、自分で記入してください\n\n"
            f"アクセス：確定次第、自分で記入してください\n\n"
            f"ぜひご参加ください！\n"
            f"引き続きよろしくお願いいたします。\n\n"
            f"幹事より"
        )
        email_text = st.text_area("案内メール文を編集してください", value=default_email, height=200)
        if st.button("メール定型文をコピー"):
            st.write("メール定型文をコピーしました！")