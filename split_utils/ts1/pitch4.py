# Author: Botao Yu

# B S O P D P D O P D B S O P D
# B S O D D O D B S O D -> B S O D P D P O D P B S O D P
# B - B
# S - S
# O - O
# D - D
# D - P

def split_sequence_pitch4(ls_list, min_target_len=None):
    src_idx = 0
    tgt_idx = 0
    src_list = []
    tgt_list = []
    align_list = []

    last_p_token = None

    for token in ls_list:
        t0 = token[0]
        if t0 == 'b':
            src_list.append(token)
            tgt_list.append(token)
            align_list.append('%d-%d' % (src_idx, tgt_idx))
            src_idx += 1
            tgt_idx += 1
        elif t0 == 's':
            src_list.append(token)
            tgt_list.append(token)
            align_list.append('%d-%d' % (src_idx, tgt_idx))
            src_idx += 1
            tgt_idx += 1
        elif t0 == 'o':
            src_list.append(token)
            tgt_list.append(token)
            align_list.append('%d-%d' % (src_idx, tgt_idx))
            src_idx += 1
            tgt_idx += 1
        elif t0 == 'p':
            last_p_token = token
        elif t0 == 'd':
            current_src_d = src_idx
            current_tgt_d = tgt_idx
            src_list.append(token)
            src_idx += 1
            tgt_list.append(token)
            tgt_idx += 1
            align_list.append('%d-%d' % (current_src_d, current_tgt_d))
            last_tgt_p = tgt_idx
            tgt_list.append(last_p_token)
            tgt_idx += 1
            align_list.append('%d-%d' % (current_src_d, last_tgt_p))
        else:
            raise ValueError("Cannot process token: %s" % token)

    if len(tgt_list) == 0 or len(src_list) == 0:
        return None, None, None
    if min_target_len is not None and len(tgt_list) - len(src_list) < min_target_len:
        return None, None, None

    return src_list, tgt_list, align_list


def restore_encoding(generated_token_str_list):
    token_str_list = generated_token_str_list[:]

    len_list = len(token_str_list)

    idx = 0
    while idx < len_list:
        token = token_str_list[idx]
        if token[0] == 'd':
            assert token_str_list[idx+1][0] == 'p', (token, token_str_list[idx+1])
            token_str_list[idx], token_str_list[idx+1] = token_str_list[idx+1], token_str_list[idx]
            idx = idx + 2
        else:
            idx = idx + 1

    return token_str_list
