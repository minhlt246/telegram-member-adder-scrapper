import sys, csv, traceback, time, re, string
import asyncio
import os
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.messages import DeleteChatUserRequest
from telethon.tl.types import ChatBannedRights, InputPeerUser, Channel, Chat
from telethon.errors import FloodWaitError
# Thư viện chính
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights, InputPeerUser
# Các hàm (Functions)
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.functions.channels import InviteToChannelRequest, EditBannedRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest # Thêm dòng này
from telethon.tl.types import InputPeerUser, Channel, Chat # Thêm Channel, Chat để kiểm tra loại nhóm
# Các định nghĩa đối tượng (Types)
from telethon.tl.types import (
    InputPeerEmpty, InputPeerChannel, InputPeerUser, 
    ChatBannedRights, ChannelParticipantsSearch
)

# Các loại lỗi (Errors)
from telethon.errors import (
    PeerFloodError, 
    UserPrivacyRestrictedError, 
    FloodWaitError, 
    SessionPasswordNeededError
)

# File cấu hình cá nhân
import configuration
client = configuration.client
client.connect()
if not client.is_user_authorized():
    client.send_code_request(configuration.phone)
    code = input('Enter verification code: ')
    try:
        client.sign_in(configuration.phone, code)
    except SessionPasswordNeededError:
        # Nếu tài khoản yêu cầu mật khẩu 2 lớp
        password = input('Số điện thoại này có mật khẩu 2 lớp. Vui lòng nhập mật khẩu: ')
        client.sign_in(password=password)
def add_users_to_group():
    """Đọc file CSV và thêm thành viên, hỗ trợ cả Nhóm nhỏ và Siêu nhóm"""
    
    input_file = input("\nNhập tên file CSV chứa danh sách muốn ADD: ")
    users = []
    try:
        with open(input_file, encoding='UTF-8') as file:
            reader = csv.reader(file)
            next(reader) 
            for row in reader:
                if len(row) < 3: continue
                users.append({
                    'id': int(row[1]),
                    'access_hash': int(row[2]),
                    'name': row[3] if len(row) > 3 else "Unknown"
                })
    except FileNotFoundError:
        print("❌ Không thấy file CSV!")
        return

    print('Đang tải danh sách nhóm...')
    dialogs = client.get_dialogs(limit=None)
    valid_groups = [d.entity for d in dialogs if d.is_group or d.is_channel]
    
    for idx, group in enumerate(valid_groups):
        print(f'{idx}: {group.title}')
    
    try:
        group_idx = int(input('\nChọn số thứ tự nhóm: '))
        target_group = valid_groups[group_idx]
    except:
        print("❌ Lựa chọn không hợp lệ.")
        return

    print(f"\n🚀 Bắt đầu thêm người vào nhóm: {target_group.title}")
    
    success = 0
    fail = 0

    for user in users:
        try:
            user_to_add = InputPeerUser(user['id'], user['access_hash'])
            
            # KIỂM TRA LOẠI NHÓM ĐỂ DÙNG LỆNH ĐÚNG
            if isinstance(target_group, Channel):
                # Đây là Siêu nhóm (Supergroup) hoặc Channel
                client(InviteToChannelRequest(target_group, [user_to_add]))
            else:
                # Đây là Nhóm nhỏ (Small Group)
                # fwd_limit=100 là số tin nhắn cũ người mới có thể xem
                client(AddChatUserRequest(target_group.id, user_to_add, fwd_limit=100))
            
            success += 1
            print(f"✅ [{success}] Đã thêm: {user['name']}")
            time.sleep(20) # Nghỉ để tránh bị khóa tài khoản
            
        except UserPrivacyRestrictedError:
            print(f"⚠️ {user['name']} chặn quyền thêm vào nhóm.")
            fail += 1
        except Exception as e:
            print(f"❌ Lỗi với {user['name']}: {e}")
            fail += 1
            if "Flood" in str(e): break
            time.sleep(2)

    print(f"\n--- HOÀN THÀNH: Thành công {success}, Thất bại {fail} ---")


def list_users_in_group():
    """Lấy thành viên theo số lượng yêu cầu, tự động quét sâu nếu bị chặn ở mốc 200"""
    
    # 1. Lấy danh sách toàn bộ hội thoại để chọn nhóm
    print('\n--- ĐANG TẢI DANH SÁCH NHÓM ---')
    dialogs = client.get_dialogs(limit=None)
    valid_groups = [d.entity for d in dialogs if d.is_group or d.is_channel]

    for idx, group in enumerate(valid_groups):
        type_str = "Supergroup" if hasattr(group, 'megagroup') and group.megagroup else "Group"
        print(f'[{idx}] {group.title} ({type_str})')

    try:
        group_idx = int(input('\nChọn số thứ tự nhóm: '))
        target_group = valid_groups[group_idx]
        required_count = int(input('Bạn muốn lấy bao nhiêu thành viên? (VD: 1000): '))
    except:
        print("❌ Lỗi nhập liệu.")
        return

    print(f'🚀 Đang bắt đầu quét {required_count} thành viên từ: {target_group.title}...')

    # --- CHẾ ĐỘ 1: QUÉT THÔNG THƯỜNG ---
    all_participants = []
    try:
        participants = client.get_participants(target_group, limit=required_count, aggressive=True)
        for p in participants:
            all_participants.append(p)
    except Exception as e:
        print(f"⚠️ Quét thông thường bị gián đoạn: {e}")

    # --- CHẾ ĐỘ 2: TỰ ĐỘNG QUÉT SÂU (Nếu bị kẹt ở mốc 200 hoặc thiếu số lượng) ---
    # Nếu kết quả trả về đúng 200 (giới hạn của Telegram) hoặc ít hơn yêu cầu
    if len(all_participants) < required_count:
        print(f"🔄 Đã lấy được {len(all_participants)} người. Tự động chuyển sang chế độ quét sâu để lấy thêm...")
        
        search_queries = string.ascii_lowercase + string.digits + " "
        
        for char in search_queries:
            if len(all_participants) >= required_count:
                break
                
            try:
                # Tìm kiếm theo từng ký tự để lách luật 200 của Telegram
                result = client.get_participants(target_group, filter=ChannelParticipantsSearch(char))
                
                new_found = 0
                for user in result:
                    if user.id not in [u.id for u in all_participants]:
                        all_participants.append(user)
                        new_found += 1
                    
                    if len(all_participants) >= required_count:
                        break
                
                if new_found > 0:
                    print(f"🔍 Đang tìm với ký tự '{char}'... Lấy thêm được {new_found} người.")
                
                # Nghỉ ngắn để tránh bị Telegram khóa (FloodWait)
                time.sleep(0.5) 
                
            except Exception:
                continue

    # --- BƯỚC CUỐI: GHI VÀO FILE CSV ---
    sanitized_title = re.sub('[^a-z0-9]+', '-', target_group.title.lower())
    filename = f'members-{sanitized_title}.csv'
    
    with open(filename, 'w', encoding='UTF-8') as file:
        writer = csv.writer(file, delimiter=',', lineterminator='\n')
        writer.writerow(['username', 'user_id', 'access_hash', 'name'])
        
        # Chỉ lấy đúng số lượng yêu cầu từ danh sách tổng
        for user in all_participants[:required_count]:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            writer.writerow([user.username or '', user.id, user.access_hash, full_name])

    print(f'\n--- HOÀN THÀNH ---')
    print(f'✅ Tổng cộng đã lấy được {len(all_participants[:required_count])} thành viên.')
    print(f'📂 Dữ liệu đã lưu vào file: {filename}')

def delete_users_from_group():
    """Xóa 500 người siêu tốc, tự động nhận diện Nhóm thường hoặc Siêu nhóm"""
    
    # --- BƯỚC 1: ĐỌC DỮ LIỆU TỪ CSV ---
    input_file = input("\nNhập tên file CSV chứa danh sách cần xóa: ")
    users = []
    try:
        with open(input_file, encoding='UTF-8') as file:
            reader = csv.reader(file)
            next(reader) 
            for row in reader:
                if len(row) < 3: continue
                users.append({
                    'id': int(row[1]), 
                    'access_hash': int(row[2]), 
                    'name': row[3] if len(row) > 3 else "Unknown"
                })
    except Exception as e:
        print(f"❌ Lỗi đọc file: {e}")
        return

    # --- BƯỚC 2: CHỌN NHÓM MỤC TIÊU ---
    print('Đang lấy danh sách nhóm...')
    dialogs = client.get_dialogs(limit=None)
    valid_groups = [d.entity for d in dialogs if d.is_group or d.is_channel]
    for idx, group in enumerate(valid_groups):
        print(f"[{idx}] {group.title}")
    
    try:
        group_idx = int(input('\nChọn số thứ tự nhóm: '))
        target_group = valid_groups[group_idx]
    except: return

    # Nhận diện loại nhóm
    is_supergroup = isinstance(target_group, Channel)
    print(f"ℹ️ Đã nhận diện: {'SIÊU NHÓM (Supergroup)' if is_supergroup else 'NHÓM THƯỜNG (Small Group)'}")

    # Lấy 500 người đầu tiên trong file
    targets = users[:500]
    print(f"\n🚀 CHẾ ĐỘ HYBRID: Chuẩn bị xóa {len(targets)} người...")
    confirm = input("Xác nhận thực hiện? (y/n): ")
    if confirm.lower() != 'y': return

    # --- BƯỚC 3: LOGIC XỬ LÝ CHÍNH ---
    async def burst_delete_chunks():
        success_count = 0
        failed_count = 0
        success_ids = [] # Để lưu lại và dọn dẹp CSV sau này
        
        chunk_size = 50 # Mỗi đợt xả 50 lệnh
        for i in range(0, len(targets), chunk_size):
            chunk = targets[i:i + chunk_size]
            tasks = []
            
            for user in chunk:
                user_peer = InputPeerUser(user['id'], user['access_hash'])
                
                if is_supergroup:
                    # Lệnh Ban cho Siêu nhóm/Kênh
                    tasks.append(client(EditBannedRequest(
                        target_group, user_peer, 
                        ChatBannedRights(until_date=None, view_messages=True)
                    )))
                else:
                    # Lệnh Kick cho Nhóm thường
                    tasks.append(client(DeleteChatUserRequest(target_group.id, user_peer)))
            
            print(f" Đang xả đợt {i//chunk_size + 1}... ({len(tasks)} lệnh)")
            
            # Gửi đồng loạt 20 lệnh
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            current_flood_wait = 0
            for idx, res in enumerate(results):
                if isinstance(res, Exception):
                    error_msg = str(res)
                    if "Flood" in error_msg:
                        # Tìm số giây cần chờ nếu dính Flood
                        wait_match = re.search(r'wait of (\d+)', error_msg)
                        if wait_match:
                            current_flood_wait = max(current_flood_wait, int(wait_match.group(1)))
                    failed_count += 1
                else:
                    success_count += 1
                    success_ids.append(str(chunk[idx]['id']))
            
            # Xử lý nghỉ giữa các đợt
            if current_flood_wait > 0:
                print(f" Dính Flood! Telegram bắt nghỉ {current_flood_wait}s...")
                await asyncio.sleep(current_flood_wait)
            else:
                # Nghỉ 2 giây "giả lập người" giữa các đợt 20 người
                await asyncio.sleep(2) 

        # Ghi log thành công vào file tạm
        if success_ids:
            with open('deleted_success.txt', 'a') as f:
                f.write('\n'.join(success_ids) + '\n')
        
        print(f"\n--- KẾT QUẢ CUỐI CÙNG ---")
        print(f" Thành công: {success_count}")
        print(f" Thất bại: {failed_count}")
        if success_count > 0:
            print(f" Đã lưu ID thành công vào 'deleted_success.txt'. Đừng quên chạy hàm 'Dọn dẹp CSV'!")

    # Chạy hàm async trong môi trường sync
    client.loop.run_until_complete(burst_delete_chunks())
def clean_csv_file():
    """Xóa bỏ những ID đã thành công khỏi file CSV gốc"""
    csv_file = input("\nNhập tên file CSV cần làm sạch: ")
    log_file = 'deleted_success.txt'
    
    if not os.path.exists(log_file):
        print("❌ Không tìm thấy file log thành công."); return

    # 1. Đọc danh sách ID đã xóa
    with open(log_file, 'r') as f:
        deleted_ids = set(line.strip() for line in f if line.strip())

    # 2. Đọc CSV và lọc
    remaining_rows = []
    header = []
    with open(csv_file, 'r', encoding='UTF-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if row[1] not in deleted_ids: # Nếu ID chưa bị xóa thì giữ lại
                remaining_rows.append(row)

    # 3. Ghi đè lại file CSV
    with open(csv_file, 'w', encoding='UTF-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(remaining_rows)

    # 4. Xóa file log để chuẩn bị cho lượt sau
    os.remove(log_file)
    print(f"🧹 Đã dọn dẹp xong! File CSV hiện còn {len(remaining_rows)} người chưa xóa.")

def display_csv():
    """Display CSV file contents"""
    with open(sys.argv[1], encoding='UTF-8') as file:
        reader = csv.reader(file, delimiter=',', lineterminator='\n')
        for row in reader:
            print(row)
    sys.exit('File display completed')


if __name__ == '__main__':
    print('\nTelegram Manager:')
    choice = int(input(
        '1. List group members\n'
        '2. Add users to group\n'
        '3. Display CSV contents\n'
        '4. Delete users from group (MỚI)\n'
        'Select option: '
    ))

    if choice == 1:
        list_users_in_group()
    elif choice == 2:
        add_users_to_group()
    elif choice == 3:
        display_csv()
    elif choice == 4:
        delete_users_from_group()
    else:
        print('Invalid selection')