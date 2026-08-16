path = r'C:\Users\6\Doubao\chats\2026-08-14\new-chat\servicepilot-demo\skills.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 匹配带空格的空行
old = '        best_intent = "other"\n        best_score = 0\n        \n        for intent, keywords in self.keyword_map.items():\n            score = sum(1 for kw in keywords if kw in message_lower)\n            if score > best_score:\n                best_score = score\n                best_intent = intent'

new = '        best_intent = "other"\n        best_score = 0\n        best_priority = 0\n        \n        for intent, keywords in self.keyword_map.items():\n            score = sum(1 for kw in keywords if kw in message_lower)\n            priority = self.priority.get(intent, 0)\n            if score > best_score or (score == best_score and score > 0 and priority > best_priority):\n                best_score = score\n                best_intent = intent\n                best_priority = priority'

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: IntentClassifier fixed')
else:
    print('STILL NOT FOUND')
