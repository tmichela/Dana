import random


def _active_human_users(client):
    """
    Fetches all users from the Zulip organization and filters them
    to include only active, non-bot users.
    Returns a dictionary mapping user_id to user_info_dict.
    """
    try:
        response = client.get_users()
        if response.get('result') != 'success':
            print(f"Error fetching users: {response.get('msg')}")
            return {}  # Return empty if API call failed
        
        all_users_data = response.get('members', [])
        active_humans = {
            u['user_id']: u
            for u in all_users_data
            if u['is_active'] and not u['is_bot']
        }
        return active_humans
    except Exception as e:
        print(f"Exception while fetching users: {e}")
        return {}


def pick_user(message, client):
    active_human_users_map = _active_human_users(client)
    if not active_human_users_map:
        return "Could not fetch user data to pick from."

    candidate_user_ids = set()

    if message['type'] == 'stream':
        stream_id = message['stream_id']
        try:
            subscribers_response = client.get_subscribers(stream_id=stream_id)
            if subscribers_response['result'] != 'success':
                return f"Error fetching subscribers: {subscribers_response['msg']}"
            
            for user_id in subscribers_response['subscribers']:
                if user_id in active_human_users_map:
                    candidate_user_ids.add(user_id)
        except Exception as e:
            print(f"Error in pick command (stream subscribers): {e}")
            return f"An error occurred while fetching stream users."

    elif message['type'] == 'private':
        recipients_in_pm = message['display_recipient']
        for user_info in recipients_in_pm:
            user_id = user_info['id']
            if user_id in active_human_users_map:
                candidate_user_ids.add(user_id)
    
    else: # Should not happen if bot only responds to DMs and stream mentions
        return "The 'pick' command can only be used in streams or private messages."

    if not candidate_user_ids:
        return "No one to pick! (Are we alone, or is everyone else a bot or inactive?)"

    chosen_user_id = random.choice(list(candidate_user_ids))
    chosen_user_info = active_human_users_map[chosen_user_id]
    
    mention = f"@**{chosen_user_info['full_name']}|{chosen_user_info['user_id']}**"
    return f"I pick {mention}!"
