"""7 nov 2026 (Mathieu : « Ace Bailey n'est pas un joueur de hockey ») : « Future Stars » n'est pas les Dallas Stars ;
Topps 2025-26 et plus = NBA ; le balayage « Ice Hockey » garde le sport que le titre dit nettement."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sports, deals
for t in ("2025-26 Topps Chrome Ace Bailey Future Stars Autograph RC", "2025-26 Topps Chrome Update Future Stars Auto Ace Bailey RC Utah Jazz",
          "2025-26 Topps Chrome Cooper Flagg RC"):
    assert sports.detecter(t, defaut="hockey") == "basketball", t
    assert deals._sport_titre(t, "hockey") == "basketball", t
for t in ("1985-86 Topps Mario Lemieux RC", "2023-24 Upper Deck Young Guns Wyatt Johnston Dallas Stars", "Jason Robertson Stars Young Guns",
          "2019-20 Upper Deck Rising Stars Jack Hughes", "2025-26 Upper Deck Splendor Ryan Leonard Rookie Auto Patch"):
    assert sports.detecter(t, defaut="hockey") == "hockey", t
assert deals._sport_titre("2024-25 SP Authentic Future Watch Auto Jakub Dobes", "hockey") == "hockey"
print("SPORT INSERTS OK")
