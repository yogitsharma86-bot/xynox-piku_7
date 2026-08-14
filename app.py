from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__)

executor = ThreadPoolExecutor(max_workers=10)
session = requests.Session()

API_KEY = os.environ.get("OUTFIT_API_KEY", "SHAPPNO")

IMAGE_TIMEOUT = 8
CANVAS_SIZE = (800, 800)
BACKGROUND_MODE = "cover"


def fetch_player_info(uid):
    url = f"https://ff-info-api-seven.vercel.app/accinfo?uid={uid}"

    try:
        response = session.get(url, timeout=IMAGE_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Player API error:", e)
        return None


def fetch_and_process_image(image_url, size=None):
    try:
        response = session.get(
            image_url,
            timeout=IMAGE_TIMEOUT
        )

        response.raise_for_status()

        image = Image.open(
            BytesIO(response.content)
        ).convert("RGBA")

        if size:
            image = image.resize(
                size,
                Image.LANCZOS
            )

        return image

    except Exception as e:
        print("Image error:", e)
        return None


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "message": "Outfit API is working",
        "endpoint": "/outfit-image"
    })


@app.route("/outfit-image", methods=["GET"])
def outfit_image():

    uid = request.args.get("uid")
    key = request.args.get("key")

    # KEY CHECK
    if not key:
        return jsonify({
            "success": False,
            "error": "Missing API key"
        }), 401

    if key != API_KEY:
        return jsonify({
            "success": False,
            "error": "Invalid API key"
        }), 401

    # UID CHECK
    if not uid:
        return jsonify({
            "success": False,
            "error": "Missing uid parameter"
        }), 400

    # PLAYER DATA
    player_data = fetch_player_info(uid)

    if not player_data:
        return jsonify({
            "success": False,
            "error": "Failed to fetch player info"
        }), 500

    profile_info = player_data.get(
        "profileInfo",
        {}
    )

    outfit_ids = (
        profile_info.get(
            "equippedSkills",
            []
        ) or []
    )

    required_starts = [
        "211",
        "214",
        "211",
        "203",
        "204",
        "205",
        "203"
    ]

    fallback_ids = [
        "211000000",
        "214000000",
        "208000000",
        "203000000",
        "204000000",
        "205000000",
        "212000000"
    ]

    used_ids = set()

    def fetch_outfit_image(index, code):

        matched = None

        for outfit_id in outfit_ids:

            outfit_id = str(outfit_id)

            if (
                outfit_id.startswith(code)
                and outfit_id not in used_ids
            ):
                matched = outfit_id
                used_ids.add(outfit_id)
                break

        if matched is None:
            matched = fallback_ids[index]

        image_url = (
            f"https://iconapi.wasmer.app/{matched}"
        )

        return fetch_and_process_image(
            image_url,
            size=(150, 150)
        )

    futures = [
        executor.submit(
            fetch_outfit_image,
            index,
            code
        )
        for index, code in enumerate(required_starts)
    ]

    # BACKGROUND IMAGE
    background_path = os.path.join(
        os.path.dirname(__file__),
        "outfit.png"
    )

    try:
        background = Image.open(
            background_path
        ).convert("RGBA")

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Background image missing",
            "details": str(e)
        }), 500

    bg_width, bg_height = background.size

    canvas_width, canvas_height = CANVAS_SIZE

    if BACKGROUND_MODE == "cover":

        scale = max(
            canvas_width / bg_width,
            canvas_height / bg_height
        )

    else:

        scale = min(
            canvas_width / bg_width,
            canvas_height / bg_height
        )

    new_width = int(bg_width * scale)
    new_height = int(bg_height * scale)

    background = background.resize(
        (new_width, new_height),
        Image.LANCZOS
    )

    offset_x = (
        canvas_width - new_width
    ) // 2

    offset_y = (
        canvas_height - new_height
    ) // 2

    canvas = Image.new(
        "RGBA",
        CANVAS_SIZE,
        (0, 0, 0, 255)
    )

    canvas.paste(
        background,
        (offset_x, offset_y),
        background
    )

    positions = [
        (350, 30, 150, 150),
        (575, 130, 150, 150),
        (665, 350, 150, 150),
        (575, 550, 150, 150),
        (350, 654, 150, 150),
        (135, 570, 150, 150),
        (135, 130, 150, 150)
    ]

    for index, future in enumerate(futures):

        try:
            image = future.result()
        except Exception:
            continue

        if not image:
            continue

        x, y, width, height = positions[index]

        x = offset_x + int(x * scale)
        y = offset_y + int(y * scale)

        width = max(
            1,
            int(width * scale)
        )

        height = max(
            1,
            int(height * scale)
        )

        image = image.resize(
            (width, height),
            Image.LANCZOS
        )

        canvas.paste(
            image,
            (x, y),
            image
        )

    output = BytesIO()

    canvas.save(
        output,
        format="PNG"
    )

    output.seek(0)

    return send_file(
        output,
        mimetype="image/png",
        download_name=f"outfit_{uid}.png"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )