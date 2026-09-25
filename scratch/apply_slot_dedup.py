import os, sys

target_file = r'c:\Users\Raysoo\Downloads\ROS_RE\mitm\local_baseapp_capture.py'
with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Normalize CRLF in content and patterns
content = content.replace('\r\n', '\n')

# 1. Add _get_appearance_slot and update _sanitize_saved_appearance_lists
target_sanitize = '''def _sanitize_saved_appearance_lists(state):
    """Remove persisted appearance IDs that have no client prop definition.

    This is deliberately a validity check, not a hard-coded outfit list.  The
    client dereferences PROP_TYPE/APPEAR for every equipped ID during hall
    construction; unknown IDs leave the model scene alive but abort the UI.
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
            if valid != original:
                rejected = [item for item in original if item not in valid]
                log('DEPOT: removed undefined equipped item(s) %s from %s' % (rejected, key))
                lists[key] = valid
                changed = True
    return changed'''

replacement_sanitize = '''def _get_appearance_slot(table, item_id):
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
    return changed'''

assert target_sanitize in content, "target_sanitize not found"
content = content.replace(target_sanitize, replacement_sanitize)

# 2. Update handle_depot_call equip and unequip logic
target_depot = '''        kind = prop_type.get('type')
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
        _save_player_state(state)'''

replacement_depot = '''        kind = prop_type.get('type')
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
        _save_player_state(state)'''

assert target_depot in content, "target_depot not found"
content = content.replace(target_depot, replacement_depot)

# 3. Add micro-pacing in send_mercury_message
target_pacing = '''    wire_sizes = []
    for index, chunk in enumerate(chunks):
        seq = first_seq + index'''

replacement_pacing = '''    wire_sizes = []
    for index, chunk in enumerate(chunks):
        if len(chunks) > 20 and index > 0 and index % 10 == 0:
            time.sleep(0.001)
        seq = first_seq + index'''

assert target_pacing in content, "target_pacing not found"
content = content.replace(target_pacing, replacement_pacing)

# Write back with CRLF
content = content.replace('\n', '\r\n')
with open(target_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully applied slot deduplication, unequip on conflict, and fragment pacing!")
