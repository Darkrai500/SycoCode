from collections import Counter
from itertools import combinations
from django.contrib.auth import get_user_model
from .models import Annotation, Assignment, Conversation, Exposure

def queue(user):
    assignments = list(Assignment.objects.filter(user=user).select_related("conversation").prefetch_related("conversation__units"))
    own = {a.unit_id: a for a in Annotation.objects.filter(user=user)}
    items = []
    for a in assignments:
        units = list(a.conversation.units.all())
        done = sum(u.id in own for u in units)
        items.append({"assignment": a, "case": a.conversation, "done": done, "total": len(units),
                      "complete": done == len(units), "started": done > 0})
    return items

def progress(user):
    items = queue(user)
    total = sum(i["total"] for i in items)
    done = sum(i["done"] for i in items)
    return {"total": total, "done": done, "remaining": total - done,
            "percent": round(100 * done / total) if total else 0,
            "groups": len(items), "complete_groups": sum(i["complete"] for i in items)}

def may_inspect(user, conversation):
    if not Assignment.objects.filter(user=user, conversation=conversation).exists():
        return True
    return Annotation.objects.filter(user=user, unit__conversation=conversation).count() == conversation.units.count()

def record_exposure(user, conversation):
    Exposure.objects.get_or_create(user=user, conversation=conversation)

def agreement_report():
    rows = list(Annotation.objects.select_related("user", "unit__conversation"))
    users = {r.user_id: r.user for r in rows}
    result = []
    for a, b in combinations(sorted(users), 2):
        for language in ["all", "es", "en"]:
            by_user = {uid: {r.unit_id: r.first_label for r in rows if r.user_id == uid
                       and (language == "all" or r.unit.conversation.language == language)} for uid in (a, b)}
            shared = sorted(by_user[a].keys() & by_user[b].keys())
            n = len(shared)
            if not n:
                continue
            left, right = [by_user[a][k] for k in shared], [by_user[b][k] for k in shared]
            po = sum(x == y for x, y in zip(left, right)) / n
            ca, cb = Counter(left), Counter(right)
            pe = sum(ca[k] * cb[k] for k in ca) / n**2
            result.append({"a": users[a].get_full_name() or users[a].username,
                           "b": users[b].get_full_name() or users[b].username,
                           "language": language, "n": n, "agreement": round(100 * po, 1),
                           "kappa": round((po-pe)/(1-pe), 4) if pe < 1 else None})
    return result
