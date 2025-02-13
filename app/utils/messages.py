# Fun feedback messages
SUCCESS_MESSAGES = [
    "✨ All done!",
    "🎉 Success!",
    "🌟 Perfect!",
    "🚀 Done!",
    "🎯 Nailed it!"
]

ERROR_MESSAGES = [
    "😅 Oops!",
    "🤔 Hmm...",
    "😬 Uh oh...",
    "🙈 Oh no!",
    "🫣 Yikes!"
]

LOADING_MESSAGES = [
    "🔄 Working on it...",
    "⚡ Almost there...",
    "🎨 Making it pretty...",
    "✨ Doing magic...",
    "🚀 Processing..."
]

def get_random_message(message_type='success'):
    """Get a random message of specified type"""
    import random
    messages = {
        'success': SUCCESS_MESSAGES,
        'error': ERROR_MESSAGES,
        'loading': LOADING_MESSAGES
    }
    return random.choice(messages.get(message_type, SUCCESS_MESSAGES)) 