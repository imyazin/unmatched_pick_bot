import json
from typing import List, Dict, Tuple, Optional


class HeroWinrateSystem:
    def __init__(self):
        with open('parser/winrates.json', 'r') as fp:
            winrates_data = json.load(fp)


        self.winrates = winrates_data
        self.hero_names = list(winrates_data.keys())
        self.num_heroes = len(self.hero_names)

    def find_hero_by_name(self, partial_name: str) -> Optional[str]:
        """Находит персонажа по частичному совпадению имени"""
        partial_name = partial_name.lower().strip()

        # Точное совпадение
        for hero in self.hero_names:
            if hero.lower() == partial_name:
                return hero

        # Частичное совпадение
        matches = [hero for hero in self.hero_names if partial_name in hero.lower()]
        return matches[0] if matches else None

    def calculate_total_winrate(self, hero: str, enemy_team: List[str]) -> float:
        """Вычисляет суммарный винрейт персонажа против команды противника"""
        if not enemy_team:
            return 0.0

        total_winrate = 0.0
        counted = 0
        for enemy in enemy_team:
            if enemy in self.winrates[hero]:
                games = self.winrates[hero][enemy]['games']
                if games >= 10:
                    total_winrate += self.winrates[hero][enemy]['percent']
                    counted += 1

        if counted == 0:
            return 0.0
        return total_winrate / counted

    def find_best_heroes(self, enemy_team: List[str], top_n: int = 10,
                             exclude_heroes: List[str] = None) -> List[Tuple[str, float]]:
        """Находит топ персонажей с максимальным винрейтом против вражеской команды"""
        if exclude_heroes is None:
            exclude_heroes = []

        # Проверяем валидность входных данных
        invalid_enemies = [char for char in enemy_team if char not in self.hero_names]
        if invalid_enemies:
            raise ValueError(f"Неизвестные персонажи в команде противника: {invalid_enemies}")

        hero_scores = []

        for hero in self.hero_names:
            if hero in exclude_heroes or hero in enemy_team:
                continue

            avg_winrate = self.calculate_total_winrate(hero, enemy_team)
            hero_scores.append((hero, avg_winrate))

        # Сортируем по убыванию винрейта
        hero_scores.sort(key=lambda x: x[1], reverse=True)

        return hero_scores[:top_n]

    def get_hero_details(self, hero: str, enemy_team: List[str]) -> Dict:
        """Получает детальную информацию о персонаже против команды противника"""
        if hero not in self.hero_names:
            raise ValueError(f"Персонаж {hero} не найден")

        details = {
            'hero': hero,
            'matchups': {},
            'average_winrate': 0.0,
            'best_matchup': None,
            'worst_matchup': None
        }

        total_winrate = 0.0
        counted = 0
        best_wr = -1.0
        worst_wr = 2.0

        for enemy in enemy_team:
            if enemy in self.winrates[hero]:
                winrate = self.winrates[hero][enemy]['percent']
                games = self.winrates[hero][enemy]['games']
                if games >= 10:
                    details['matchups'][enemy] = {}
                    details['matchups'][enemy]['winrate'] = winrate
                    details['matchups'][enemy]['games'] = games
                    total_winrate += winrate
                    counted += 1

                    if winrate > best_wr:
                        best_wr = winrate
                        details['best_matchup'] = (enemy, winrate)

                    if winrate < worst_wr:
                        worst_wr = winrate
                        details['worst_matchup'] = (enemy, winrate)

        if counted > 0:
            details['average_winrate'] = total_winrate / counted

        return details

def main():
    system = HeroWinrateSystem()

    # Пример команды противника
    enemy_team = ["Achilles", "Buffy", "Geralt of Rivia", "Tomoe Gozen"]

    print("=== КОМАНДА ПРОТИВНИКА ===")
    print(f"Противники: {', '.join(enemy_team)}")
    print()

    # Находим лучших персонажей
    print("=== ТОП 10 ПЕРСОНАЖЕЙ ПРОТИВ ЭТОЙ КОМАНДЫ ===")
    best_heroes = system.find_best_heroes(enemy_team, top_n=10)

    for i, (hero, winrate) in enumerate(best_heroes, 1):
        print(f"{i:2d}. {hero:15s} - {winrate:.1%} средний винрейт")

    print()

    # Детальная информация о топ-3 персонажах
    print("=== ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О ТОП-5 ===")
    for i, (hero, avg_winrate) in enumerate(best_heroes[:5], 1):
        details = system.get_hero_details(hero, enemy_team)
        print(f"\n{i}. {hero} (средний винрейт: {avg_winrate:.1%})")
        print("   Матчапы:")
        for enemy, winrate in details['matchups'].items():
            print(f"     vs {enemy}: {winrate:.1%}")
        print(f"   Лучший матчап: vs {details['best_matchup'][0]} ({details['best_matchup'][1]:.1%})")
        print(f"   Худший матчап: vs {details['worst_matchup'][0]} ({details['worst_matchup'][1]:.1%})")


if __name__ == "__main__":
    main()