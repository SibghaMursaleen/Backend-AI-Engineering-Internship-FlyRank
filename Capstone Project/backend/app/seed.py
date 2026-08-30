from app.db.session import SessionLocal
from app.models.billing import Plan

def seed_plans():
    db = SessionLocal()
    try:
        # 1. Seed Free Plan
        free_plan = db.query(Plan).filter(Plan.id == "free").first()
        if not free_plan:
            free_plan = Plan(
                id="free",
                name="Free Plan",
                monthly_quota=1000,
                price_cents=0
            )
            db.add(free_plan)
            print("Seeded: Free Plan")
        else:
            print("Free Plan already exists")

        # 2. Seed Pro Plan
        pro_plan = db.query(Plan).filter(Plan.id == "pro").first()
        if not pro_plan:
            pro_plan = Plan(
                id="pro",
                name="Pro Plan",
                monthly_quota=50000,
                price_cents=2900  # $29.00
            )
            db.add(pro_plan)
            print("Seeded: Pro Plan")
        else:
            print("Pro Plan already exists")

        db.commit()
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting database seeding...")
    seed_plans()
    print("Database seeding completed.")
