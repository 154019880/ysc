import re
import os
import zipfile
from telethon.sync import TelegramClient
from telethon.tl.types import Document, DocumentAttributeFilename
from tqdm import tqdm
import time
import shutil
import json
import difflib
from datetime import datetime

# ������Ϣ
api_id = '27335138'
api_hash = '2459555ba95421148c682e2dc3031bb6'
phone = "+86 15896020219"
channel = 'https://t.me/PandaGroovePG'
group_username = '@pgzdsc'  # �޸�Ϊʵ�ʵ�Ⱥ���û���
download_path = '/www/xzqzy/lib1/pgdown'  # ����·��
target_path = '/www/xzqzy/lib1'  # Ŀ��·��
filter = r".*\.zip"  # �ļ����˹���

# ȷ�� session �ļ�·����ȷ
session_file = '/www/pgsc/pg.session'

client = TelegramClient(session_file, api_id, api_hash)

def progress_callback(current, total):
    if not hasattr(progress_callback, "pbar") or progress_callback.pbar is None:
        progress_callback.pbar = tqdm(total=total, unit="B", unit_scale=True, desc="Downloading")
    progress_callback.pbar.n = current
    progress_callback.pbar.refresh()

def close_progress_bar():
    if hasattr(progress_callback, "pbar") and progress_callback.pbar is not None:
        progress_callback.pbar.close()
        progress_callback.pbar = None

def get_file_mtime(file_path):
    """��ȡ�ļ�������޸�ʱ��"""
    return os.path.getmtime(file_path)

def extract_zip_with_timestamps(zip_path, extract_to):
    """��ѹ�ļ�������ԭʼʱ����Ϣ"""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for zip_info in zip_ref.infolist():
            # ��ѹ�ļ�
            zip_ref.extract(zip_info, extract_to)
            # �����ļ����޸�ʱ��ͷ���ʱ��
            file_path = os.path.join(extract_to, zip_info.filename)
            mod_time = time.mktime(zip_info.date_time + (0, 0, -1))
            os.utime(file_path, (mod_time, mod_time))

async def download_and_extract_latest_file():
    messages = await client.get_messages(channel, limit=10)
    zip_files = []

    for message in messages:
        if message.document and isinstance(message.document, Document):
            if message.document.mime_type == 'application/zip':
                file_name = None
                for attribute in message.document.attributes:
                    if isinstance(attribute, DocumentAttributeFilename):
                        file_name = attribute.file_name

                if file_name and re.match(filter, file_name):
                    zip_files.append((message, file_name))

    zip_files.sort(key=lambda x: x[0].date, reverse=True)

    if zip_files:
        latest_message, latest_file_name = zip_files[0]
        latest_file_path = os.path.join(download_path, latest_file_name)

        print(f"��⵽���µ�ѹ�����ļ���: {latest_file_name}")
        print(f"����Ŀ���ļ����е��ļ���: {os.path.basename(latest_file_path)}")

        # ����ļ��Ƿ��Ѵ���
        if os.path.exists(latest_file_path):
            print(f"�ļ� {latest_file_name} �Ѵ��ڣ����ʱ���...")
            existing_file_mtime = get_file_mtime(latest_file_path)
            latest_file_mtime = time.mktime(latest_message.date.timetuple())
            print(f"�����ļ�ʱ���: {existing_file_mtime}")
            print(f"Telegram Ƶ�����ļ�ʱ���: {latest_file_mtime}")
            if existing_file_mtime >= latest_file_mtime:
                print(f"�����ļ�ʱ������£���������")
                return
            else:
                print(f"�����ļ�ʱ����Ͼɣ�����������")
        else:
            print(f"�����ļ������ڣ����������ļ�: {latest_file_name}")

        print(f"׼���������ļ�: {latest_file_name}")
        try:
            await client.download_media(latest_message, latest_file_path, progress_callback=progress_callback)
            print(f"�ļ��������: {latest_file_path}")
        finally:
            close_progress_bar()

        # ��ѹ�ļ�������·����������ԭʼʱ����Ϣ
        extract_zip_with_timestamps(latest_file_path, download_path)
        print(f"�ļ��ѽ�ѹ�� {download_path}���������ļ���ԭʼ�޸�����")

        # ɾ���ɵ�ѹ�������������µģ�
        await delete_all_zip_files(latest_file_name)

        # �Ƚ��ļ�ʱ����Ϣ������
        await update_files_with_time_comparison(latest_file_name, latest_message.text)
    else:
        print("û�з����������ļ�")

async def delete_all_zip_files(latest_file_name=None):
    print("��ʼ����ɵ�ѹ����...")
    zip_files = [f for f in os.listdir(download_path) if f.endswith('.zip')]
    for old_zip in zip_files:
        if old_zip == latest_file_name:
            print(f"��������ѹ����: {old_zip}")
            continue
        old_zip_path = os.path.join(download_path, old_zip)
        os.remove(old_zip_path)
        print(f"��ɾ����ѹ����: {old_zip}")

async def compare_and_upload_files(old_file, new_file):
    try:
        with open(old_file, 'r', encoding='utf-8') as f1, open(new_file, 'r', encoding='utf-8') as f2:
            old_lines = f1.readlines()
            new_lines = f2.readlines()
        added_lines = [line for line in new_lines if line not in old_lines]
        deleted_lines = [line for line in old_lines if line not in new_lines]
        if added_lines or deleted_lines:
            change_log = ""
            if added_lines:
                change_log += "�����������£�\n" + "\n".join([line.rstrip() for line in added_lines]) + "\n"
            if deleted_lines:
                change_log += "ɾ���������£�\n" + "\n".join([line.rstrip() for line in deleted_lines]) + "\n"
            return change_log
        else:
            return None
    except Exception as e:
        print(f"�Ա��ļ�ʱ����{e}")
        return None

async def send_message_in_parts(client, entity, message, max_length=4096):
    while message:
        part = message[:max_length]
        message = message[max_length:]
        await client.send_message(entity, part)
        if message:
            time.sleep(1)  # ���ⷢ�͹��쵼�µ�����

async def update_files_with_time_comparison(latest_file_name, message_text):
    print("��ʼ�Ա��ļ�ʱ����Ϣ������...")
    update_files = []
    jsm_diff = []
    jsm_updated = False

    # ��������·���е������ļ����������ļ����ڵ��ļ���
    for root, dirs, files in os.walk(download_path):
        for file in files:
            download_file_path = os.path.join(root, file)
            # Ŀ���ļ����е��ļ�·�����������ļ��нṹ��
            target_file_path = os.path.join(target_path, os.path.basename(file))

            # �������µ�ѹ����
            if file == latest_file_name:
                print(f"��������ѹ���� {latest_file_name}����������Ŀ���ļ���")
                continue

            # ����ļ��Ƿ����
            if not os.path.exists(download_file_path):
                print(f"�ļ������ڣ�����: {download_file_path}")
                continue

            # ���Ŀ���ļ��Ƿ���ڲ��Ƚ�ʱ����Ϣ
            if os.path.exists(target_file_path):
                if get_file_mtime(download_file_path) != get_file_mtime(target_file_path):
                    # ʱ����Ϣ�в��죬��¼�ļ���
                    update_files.append(file)
            else:
                # �ļ������ڣ�ֱ�Ӽ�¼
                update_files.append(file)

            # �ر��� jsm.json �ļ�����¼���ݲ���
            if file == "jsm.json":
                old_jsm_path = os.path.join(target_path, "jsm.json")
                new_jsm_path = download_file_path
                diff_log = await compare_and_upload_files(old_jsm_path, new_jsm_path)
                if diff_log:
                    jsm_diff.append(diff_log)
                    jsm_updated = True

    # ��� jsm.json �и��£���¼�������ļ��б���
    if jsm_updated:
        update_files.append("jsm.json")

    # �������µ��ļ���Ŀ���ļ���
    for file in update_files:
        # ���¼��������ļ���·�����������ļ��У�
        for root, dirs, files in os.walk(download_path):
            if file in files:
                download_file_path = os.path.join(root, file)
                target_file_path = os.path.join(target_path, file)
                if os.path.exists(download_file_path):
                    shutil.copy2(download_file_path, target_file_path)
                    print(f"�ļ� {file} �Ѹ��µ�Ŀ���ļ���")
                else:
                    print(f"�ļ������ڣ��޷�����: {download_file_path}")
                break

    # ׼��������Ϣ
    attachment_info = f"PG���°汾��{latest_file_name}\n"
    update_info = f"���µ��ļ��У�{', '.join(update_files)}\n" if update_files else "���ļ�����\n"
    content_info = message_text.split('���ո�������', 1)[1] if '���ո�������' in message_text else "�޸�������"
    if 'jsm.json' in update_files and jsm_diff:
        update_info += f"jsm.json�ļ��仯���ݣ�\n{''.join(jsm_diff)}\n"
    full_message = attachment_info + update_info + content_info

    # ������Ϣ��Ⱥ��
    await send_message_in_parts(client, group_username, full_message)
    print(f"������Ϣ��ת����Ⱥ�飺{group_username}")

with client:
    client.start(phone=phone)
    if not client.is_user_authorized():
        print("�û�δ��Ȩ����Ҫ�ֶ�������֤��")
        client.send_code_request(phone)
        code = input('Please enter the code you received: ')
        client.sign_in(phone, code)
    else:
        print("�û�����Ȩ��ֱ��ʹ�� session �ļ�")
    client.loop.run_until_complete(download_and_extract_latest_file())