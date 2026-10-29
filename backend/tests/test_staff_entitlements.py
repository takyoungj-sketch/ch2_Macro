from app.platform.entitlements import apply_staff_entitlements


def test_admin_opens_both_products_without_a_subscription_row():
    opened = apply_staff_entitlements("admin", {"macro": False, "fieldnote": False})
    assert opened == {"macro": True, "fieldnote": True}


def test_member_entitlements_stay_unchanged():
    ent = {"macro": False, "fieldnote": True}
    assert apply_staff_entitlements("member", ent) is ent
