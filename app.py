import os
import uuid
import requests
from flask import Flask, request, render_template, redirect, session, url_for, flash
from dotenv import load_dotenv
from supabase_config import supabase
from replicate_api import cartoonify_image
from datetime import datetime
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

def increment_visits():
    try:
        row = supabase.table("visits").select("*").eq("id", 1).execute()
        if row.data:
            current_count = row.data[0]["count"]
            supabase.table("visits").update({"count": current_count + 1}).eq("id", 1).execute()
    except Exception as e:
        print("خطأ أثناء تسجيل الزيارة:", e)

@app.route('/')
def home():
    increment_visits()
    return render_template("index.html")

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin-login')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin')
        else:
            flash("بيانات الدخول غير صحيحة", "error")
    return render_template('admin_login.html')

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin-login')

    subs = supabase.table("subscriptions")\
        .select("user_id,status,created_at,email")\
        .execute().data
    imgs = supabase.table("images")\
        .select("user_id")\
        .execute().data

    total_users    = len(subs)
    paid_users     = sum(1 for s in subs if s["status"]=="paid")
    free_users     = total_users - paid_users
    total_images   = len(imgs)
    total_earnings = paid_users * 3  # غيّر السعر لو حابب

    # ✅ إضافة: حساب عدد زوار الموقع
    try:
        visits_data = supabase.table("visits").select("count").eq("id", 1).execute()
        visits_count = visits_data.data[0]["count"] if visits_data.data else 0
    except:
        visits_count = 0

    users = []
    for s in subs:
        uid        = s["user_id"]
        status     = s["status"]
        email      = s["email"]
        created_at = s["created_at"][:16].replace("T"," ")
        cnt        = sum(1 for i in imgs if i["user_id"]==uid)
        users.append({
            "id": uid, "email": email,
            "status": status,
            "created_at": created_at,
            "image_count": cnt
        })

    return render_template("admin.html",
        total_users=total_users,
        paid_users=paid_users,
        free_users=free_users,
        total_images=total_images,
        total_earnings=total_earnings,
        users=users,
        visits_count=visits_count  # ✅ تمرير المتغير للقالب
    )


@app.route('/admin/upgrade', methods=['POST'])
def admin_upgrade():
    if not session.get('admin'):
        return redirect('/admin-login')
    uid = request.form['user_id']
    supabase.table('subscriptions') \
        .update({"status": "paid"}) \
        .eq("user_id", uid).execute()
    return redirect('/admin')

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if not session.get('admin'):
        return redirect('/admin-login')
    uid = request.form['user_id']
    # حذف الصور والاشتراك
    supabase.table('images').delete().eq("user_id", uid).execute()
    supabase.table('subscriptions').delete().eq("user_id", uid).execute()
    return redirect('/admin')


@app.route('/admin/upgrade', methods=['POST'])
def admin_upgrade_user():
    if not session.get('admin'):
        return redirect('/admin-login')

    user_id = request.form.get('user_id')
    try:
        supabase.table("subscriptions").update({"status": "paid"}).eq("user_id", user_id).execute()
        flash("تم ترقية المستخدم بنجاح", "success")
    except Exception as e:
        flash(f"فشل في الترقية: {str(e)}", "error")

    return redirect('/admin')

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email    = request.form['email'].strip()
        password = request.form['password']

        if not email or not password:
            flash("يرجى إدخال البريد الإلكتروني وكلمة المرور.", "error")
            return render_template('signup.html')

        try:
            # 1. تسجيل المستخدم في Supabase Auth
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            user = response.user
            if not user:
                flash("فشل إنشاء الحساب. تحقق من البريد الإلكتروني.", "error")
                return render_template('signup.html')

            user_id = user.id

            # 2. حفظ الاشتراك المجاني مع البريد في جدول subscriptions
            supabase.table('subscriptions').insert({
                "user_id": user_id,
                "status":  "free",
                "email":   email
            }).execute()

            # 3. تهيئة الجلسة والانتقال للـ dashboard
            session['user']    = email
            session['user_id'] = user_id
            return redirect('/dashboard')

        except Exception as e:
            print("Signup error:", e)
            flash("حدث خطأ أثناء إنشاء الحساب: " + str(e), "error")

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if auth_response.session:
                session['user'] = email
                session['user_id'] = auth_response.user.id
                return redirect('/dashboard')
            else:
                flash("خطأ في الدخول. تحقق من البريد وكلمة المرور.", "error")

        except Exception as e:
            flash("فشل تسجيل الدخول: " + str(e), "error")

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    user_id = session['user_id']
    plan = 'free'

    result = supabase.table('subscriptions').select("status").eq("user_id", user_id).execute()
    if result.data:
        plan = result.data[0]['status']

    images_result = supabase.table('images')\
        .select("cartoon_url, created_at")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .execute()

    images = images_result.data if images_result else []
    return render_template('dashboard.html', user=session['user'], plan=plan, images=images)


@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    email = session['user']

    # التحقق من الاشتراك
    sub_status = supabase.table('subscriptions').select("status").eq("user_id", user_id).execute()
    status = sub_status.data[0]["status"] if sub_status.data else "free"

    # محاولة مجانية واحدة فقط
    if status == "free":
        try_check = supabase.table("free_tries").select("*").eq("user_id", user_id).execute()
        if try_check.data and try_check.data[0]["used"]:
            flash("لقد استخدمت تحويلك المجاني. اشترك للوصول غير المحدود.", "error")
            return redirect('/pay')

    # التحقق من الصورة
    image = request.files['image']
    if image.filename == '':
        flash('لم يتم اختيار صورة', 'error')
        return redirect('/dashboard')

    # رفع الصورة الأصلية مؤقتًا إلى Supabase
    original_filename = f"{uuid.uuid4()}.jpg"
    supabase.storage.from_('images').upload(original_filename, image.read())
    original_url = supabase.storage.from_('images').get_public_url(original_filename)

    # تحويل الصورة
    cartoon_url = cartoonify_image(original_url)

    # حذف الصورة الأصلية بعد التحويل
    supabase.storage.from_('images').remove([original_filename])

    if not cartoon_url:
        flash("فشل في معالجة الصورة عبر الذكاء الاصطناعي. حاول مجددًا.", "error")
        return redirect('/dashboard')

    # تحميل الصورة المعدلة إلى Supabase
    cartoon_response = requests.get(cartoon_url)
    if cartoon_response.status_code != 200:
        flash("فشل تحميل الصورة المعدلة.", "error")
        return redirect('/dashboard')

    cartoon_filename = f"{uuid.uuid4()}.jpg"
    supabase.storage.from_('images').upload(cartoon_filename, cartoon_response.content)
    cartoon_final_url = supabase.storage.from_('images').get_public_url(cartoon_filename)

    # حفظ الصورة للمشترك فقط
    if status == "paid":
        supabase.table("images").insert({
            "user_id": user_id,
            "cartoon_url": cartoon_final_url
        }).execute()

    # تفعيل التجربة المجانية إن لم تكن مستخدمة
    if status == "free":
        if not try_check.data:
            supabase.table("free_tries").insert({"user_id": user_id, "used": True}).execute()
        else:
            supabase.table("free_tries").update({"used": True}).eq("user_id", user_id).execute()

    return render_template("result.html", cartoon=cartoon_final_url, plan=status)

@app.route('/delete_image', methods=['POST'])
def delete_image():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    image_url = request.form['image_url']
    file_name = image_url.split('/')[-1].split('?')[0]

    try:
        supabase.storage.from_('images').remove([file_name])
        supabase.table('images')\
            .delete()\
            .eq('user_id', user_id)\
            .eq('cartoon_url', image_url)\
            .execute()

        flash("تم حذف الصورة بنجاح.", "success")
    except Exception as e:
        flash("فشل في حذف الصورة.", "error")
        print("Delete error:", str(e))

    return redirect('/dashboard')


@app.route('/pay')
def pay():
    if 'user' not in session:
        return redirect('/login')
    return render_template('pay.html', user=session['user'])

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        return "Unauthorized", 401

    session["payment_verified"] = True
    return "OK"

@app.route('/confirm_payment')
def confirm_payment():
    if 'user_id' not in session:
        return redirect('/login')

    if not session.get("payment_verified"):
        flash("لا يمكنك الوصول إلى هذه الصفحة مباشرة.", "error")
        return redirect("/dashboard")

    session.pop("payment_verified", None)  # إزالة الجلسة بعد الاستخدام

    supabase.table('subscriptions')\
        .update({"status": "paid"})\
        .eq("user_id", session['user_id'])\
        .execute()

    return render_template("confirmed_payment.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

if __name__ == '__main__':
    app.run(debug=True)