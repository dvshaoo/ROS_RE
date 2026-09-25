import sys

file_path = 'mitm/local_baseapp_capture.py'
with open(file_path, 'rb') as f:
    raw = f.read()

# Work with LF in memory
crlf = b'\r\n' in raw
text = raw.decode('utf-8').replace('\r\n', '\n')

# 1. Update _load_player_state and insert _get_appearance_slot + _sanitize_saved_appearance_lists
part1_old = '''def _load_player_state():
    try:
        with open(_player_state_path, encoding='utf-8') as f:
            state = json.load(f)
        if isinstance(state, dict):
            return state
    except (OSError, ValueError):
        pass
    return {'gender': 1, 'lists': {'1': {'wear': [], 'body': []}, '2': {'wear': [], 'body': []}}}


def _save_player_state(state):
    os.makedirs(os.path.dirname(_player_state_path), exist_ok=True)
    temp = _player_state_path + '.tmp'
    with open(temp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write('\\n')
    os.replace(temp, _player_state_path)'''

part1_new = '''def _get_appearance_slot(table, item_id):
    rec = table.get(item_id, {}).get('value', {})
    prop_type = rec.get('PROP_TYPE', {})
    kind = prop_type.get('type')
    category = prop_type.get('value', {}).get('CATEGORY')

    if kind == 'WearableApperanceType':
        if category in (None, 1):
            return 'head'
        elif category in (2, 5, 6):
            return 'top'
        elif category in (3, 7, 8):
            return 'bottom'
        elif category == 4:
            return 'shoes'
        return 'wearable_%s' % category
    elif kind == 'BobyAppearanceType':
        if category in (None, 1):
            return 'face'
        elif category == 2:
            return 'hair'
        elif category == 3:
            return 'gender'
        return 'body_%s' % category
    elif kind == 'DecorationAppearanceType':
        if category in (None, 11):
            return 'mask'
        elif category == 12:
            return 'glasses'
        return 'decoration_%s' % category
    return None


def _sanitize_saved_appearance_lists(state):
    """Remove persisted appearance IDs that have no client prop definition,
    and deduplicate so only one item per slot (head, top, bottom, etc.) can be worn.
    """
    try:
        table = _prop_tables().get(0xa2f095a2, {})
    except Exception as e:
        log('DEPOT: skipped appearance-list validation: %r' % (e,))
        return False
    changed = False
    for lists in (state.get('lists') or {}).values():
        if not isinstance(lists, dict):
            continue
        for key in ('wear', 'body'):
            original = lists.get(key, [])
            if not isinstance(original, list):
                lists[key] = []
                changed = True
                continue
            valid = [item for item in original
                     if isinstance(item, int) and table.get(item, {}).get('value', {}).get('PROP_TYPE')]
            # Deduplicate by slot keeping the most recently equipped item
            seen_slots = set()
            deduped = []
            for item in reversed(valid):
                slot = _get_appearance_slot(table, item)
                if slot is not None:
                    if slot in seen_slots:
                        log('DEPOT: sanitizing duplicate slot %r (dropped %d in favor of %s)' % (slot, item, deduped))
                        continue
                    seen_slots.add(slot)
                deduped.append(item)
            deduped.reverse()
            if deduped != original:
                rejected = [item for item in original if item not in deduped]
                log('DEPOT: removed invalid/duplicate item(s) %s from %s' % (rejected, key))
                lists[key] = deduped
                changed = True
    return changed


def _load_player_state():
    try:
        with open(_player_state_path, encoding='utf-8') as f:
            state = json.load(f)
        if isinstance(state, dict):
            if _sanitize_saved_appearance_lists(state):
                _save_player_state(state)
            return state
    except (OSError, ValueError):
        pass
    return {'gender': 1, 'lists': {'1': {'wear': [], 'body': []}, '2': {'wear': [], 'body': []}}}


def _save_player_state(state):
    os.makedirs(os.path.dirname(_player_state_path), exist_ok=True)
    temp = _player_state_path + '.tmp'
    with open(temp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write('\\n')
    os.replace(temp, _player_state_path)'''

assert part1_old in text, 'part1_old not found in text'
text = text.replace(part1_old, part1_new)

# 2. Update handle_depot_call equip and unequip logic
part2_old = '''    with _player_state_lock:
        state = _load_player_state()
        gender = int(state.get('gender', 1))
        current = state.setdefault('lists', {}).setdefault(str(gender), {'wear': [], 'body': []})
        table = _prop_tables().get(0xa2f095a2, {})
        prop_type = table.get(value, {}).get('value', {}).get('PROP_TYPE', {})
        kind = prop_type.get('type')
        category = prop_type.get('value', {}).get('CATEGORY')
        target = current.setdefault('body' if kind == 'BodyApperanceType' else 'wear', [])
        if name == 'equipAppearance':
            if category is not None:
                for old in target[:]:
                    old_category = table.get(old, {}).get('value', {}).get('PROP_TYPE', {}).get('value', {}).get('CATEGORY')
                    if old_category == category:
                        target.remove(old)
            if value not in target:
                target.append(value)
            reply = 356  # onNotifyEquipedAppearance
        else:
            if value in target:
                target.remove(value)
            reply = 357  # onNotifyUnloadAppearance
        _save_player_state(state)
        wear, body = current.get('wear', []), current.get('body', [])'''

part2_new = '''    with _player_state_lock:
        state = _load_player_state()
        gender = int(state.get('gender', 1))
        current = state.setdefault('lists', {}).setdefault(str(gender), {'wear': [], 'body': []})
        table = _prop_tables().get(0xa2f095a2, {})
        prop_type = table.get(value, {}).get('value', {}).get('PROP_TYPE', {})
        if not prop_type:
            log('DEPOT: ignored %s for undefined appearance item=%d' % (name, value))
            return
        kind = prop_type.get('type')
        slot = _get_appearance_slot(table, value)
        wear_list = current.setdefault('wear', [])
        body_list = current.setdefault('body', [])
        target = body_list if kind == 'BobyAppearanceType' else wear_list
        if name == 'equipAppearance':
            # Strictly enforce single item per slot: unequip any existing item in that slot
            if slot is not None:
                for old in wear_list[:]:
                    if _get_appearance_slot(table, old) == slot:
                        wear_list.remove(old)
                        log('DEPOT: auto-unequipped conflicting item=%d from wear (slot=%s)' % (old, slot))
                for old in body_list[:]:
                    if _get_appearance_slot(table, old) == slot:
                        body_list.remove(old)
                        log('DEPOT: auto-unequipped conflicting item=%d from body (slot=%s)' % (old, slot))
            if value not in target:
                target.append(value)
            reply = 356  # onNotifyEquipedAppearance
        else:
            if value in wear_list:
                wear_list.remove(value)
            if value in body_list:
                body_list.remove(value)
            reply = 357  # onNotifyUnloadAppearance
        _save_player_state(state)
        wear, body = current.get('wear', []), current.get('body', [])'''

assert part2_old in text, 'part2_old not found in text'
text = text.replace(part2_old, part2_new)

# 3. Add micro-pacing in send_mercury_message
part3_old = '''    wire_sizes = []
    for index, chunk in enumerate(chunks):
        seq = first_seq + index'''

part3_new = '''    wire_sizes = []
    for index, chunk in enumerate(chunks):
        if len(chunks) > 20 and index > 0 and index % 10 == 0:
            time.sleep(0.001)
        seq = first_seq + index'''

assert part3_old in text, 'part3_old not found in text'
text = text.replace(part3_old, part3_new)

if crlf:
    text = text.replace('\n', '\r\n')

with open(file_path, 'wb') as f:
    f.write(text.encode('utf-8'))

print('Successfully applied patch to mitm/local_baseapp_capture.py!')
