"""Create a private demo trip. Run after `alembic upgrade head`."""

import argparse
import secrets
from datetime import timedelta

from app.core import digest, make_session, public_origin
from app.decisions_models import Comment, Poll, PollOption, PollRound
from app.models import Invitation, Membership, Trip, User, utcnow
from app.planning import append_item
from app.planning_models import Candidate, Place, TripDay


def seed_demo(owner_id=None, hours=24):
    origin = public_origin()
    if not 1 <= hours <= 168:
        raise ValueError("邀請時效必須為 1 到 168 小時。")
    with make_session() as db, db.begin():
        if owner_id:
            owner = db.get(User, owner_id)
            if not owner or owner.account_type != "google":
                raise ValueError("找不到指定的 Google 使用者，請確認帳號已登入過本站。")
        else:
            # An unclaimable curator holds the sample entries. The CLI issues only a member invitation.
            owner = User(account_type="guest", nickname="示範行程編輯")
            db.add(owner)
            db.flush()
        trip = Trip(
            owner_id=owner.id,
            title="台南巷弄小旅行",
            destinations=["台灣", "台南"],
            cover="tainan",
            description="沿著府城散步，最後在安平看夕陽。",
        )
        db.add(trip)
        db.flush()
        db.add(Membership(trip_id=trip.id, user_id=owner.id, role="owner"))
        days = [
            TripDay(trip_id=trip.id, day_number=i, title=title)
            for i, title in enumerate(["走進府城", "安平日落"], start=1)
        ]
        db.add_all(days)
        db.flush()
        stops = [
            ("神農街", 22.9976, 120.1971, "中西區神農街", 0, "15:00"),
            ("水仙宮市場", 22.9970, 120.1985, "中西區海安路二段", 0, "17:00"),
            ("安平古堡", 23.0015, 120.1609, "安平區國勝路", 1, "10:00"),
            ("漁光島", 22.9781, 120.1560, "安平區漁光路", 1, "16:30"),
        ]
        places = []
        for name, latitude, longitude, address, day_index, start in stops:
            place = Place(
                trip_id=trip.id,
                created_by=owner.id,
                editable_by=owner.id,
                name=name,
                city="台南",
                country="台灣",
                latitude=latitude,
                longitude=longitude,
                address=address,
                category="place",
                duration=60,
            )
            db.add(place)
            db.flush()
            db.add(Candidate(trip_id=trip.id, place_id=place.id, status="want"))
            item = append_item(db, trip.id, owner.id, days[day_index].id, name, "place", place.id)
            item.start_time, item.duration = start, 60
            places.append(place)
        poll = Poll(trip_id=trip.id, created_by=owner.id, editable_by=owner.id)
        db.add(poll)
        db.flush()
        round_ = PollRound(
            poll_id=poll.id,
            number=1,
            title="哪個地方想多留一小時？",
            kind="place",
            mode="single",
            deadline=utcnow() + timedelta(hours=hours),
        )
        db.add(round_)
        db.flush()
        db.add_all(
            [
                PollOption(
                    round_id=round_.id,
                    option_text=p.name,
                    place_id=p.id,
                    created_by=owner.id,
                    ordinal=i,
                )
                for i, p in enumerate(places)
            ]
        )
        db.add(
            Comment(
                trip_id=trip.id,
                author_id=owner.id,
                content="想去哪裡看夕陽？歡迎新增景點，或在投票中提出想法。",
            )
        )
        code = "".join(secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(12))
        db.add(
            Invitation(
                trip_id=trip.id,
                token_hash=digest(code),
                expires_at=utcnow() + timedelta(hours=hours),
            )
        )
        return {"trip_id": trip.id, "url": origin + "/?invite=" + code}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="建立一趟獨立的台南展示旅程並產生限時成員邀請。")
    parser.add_argument("--owner-id", help="指定已登入過的 Google 使用者 UUID 為擁有者")
    parser.add_argument("--hours", default=24, type=int, help="邀請時效（1–168 小時）")
    args = parser.parse_args()
    try:
        result = seed_demo(args.owner_id, args.hours)
    except ValueError as error:
        parser.error(str(error))
    print(f"旅程 {result['trip_id']}\n{args.hours} 小時內可加入：{result['url']}")
