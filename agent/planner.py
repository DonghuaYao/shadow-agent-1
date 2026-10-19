
def plan_next_action(elements, goals):
    """Find a UI target and its clickable ancestor."""

    if isinstance(goals, str):
        goals = [goals]

    for goal in goals:
        for element in elements:
            text = element["text"].strip().lower()
            description = element["description"].strip().lower()

            if text == goal.lower() or description == goal.lower():
                center = element.get("tap_center")

                if center:
                    return {
                        "action": "tap",
                        "target": goal,
                        "center": center,
                    }

    return {
        "action": "not_found",
        "target": goals,
        "center": None,
    }
