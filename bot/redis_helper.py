import json


class RedisHelper:
    def __init__(self, redis_client):
        self.redis = redis_client

    def add_character_to_bans_list(self, user_id: int, character: str):
        """Добавляет персонажа в список банов пользователя"""
        key = f"bans_list:{user_id}"

        bans_list = self.redis.get(key)
        if bans_list:
            bans_list = json.loads(bans_list)
        else:
            bans_list = []

        bans_list.append(character)
        self.redis.set(key, json.dumps(bans_list, ensure_ascii=False))

        return len(bans_list)

    def get_bans_list(self, user_id: int):
        """Получает весь список банов пользователя"""
        key = f"bans_list:{user_id}"
        bans_list = self.redis.get(key)

        if bans_list:
            return json.loads(bans_list)
        else:
            return []

    def clear_bans_list(self, user_id: int):
        """Очищает список банов пользователя"""
        key = f"bans_list:{user_id}"
        self.redis.delete(key)

    def remove_character_from_bans_list(self, user_id: int, character: str):
        """Удаляет персонажа из списка банов пользователя (если есть)"""
        key = f"bans_list:{user_id}"
        bans_list_raw = self.redis.get(key)
        if not bans_list_raw:
            return 0
        bans_list = json.loads(bans_list_raw)
        if character in bans_list:
            bans_list = [c for c in bans_list if c != character]
            self.redis.set(key, json.dumps(bans_list, ensure_ascii=False))
        return len(bans_list)

    def is_character_banned(self, user_id: int, character: str) -> bool:
        """Проверяет, забанен ли персонаж у пользователя"""
        bans = self.get_bans_list(user_id)
        return character in bans

    def set_bans_list(self, user_id: int, bans_list):
        """Полностью перезаписывает список банов пользователя"""
        key = f"bans_list:{user_id}"
        self.redis.set(key, json.dumps(bans_list, ensure_ascii=False))