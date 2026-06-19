#!/usr/bin/env python3
"""
Quick bot config verification script.
Run: python debug_bot.py
"""

import sys
import os
from pathlib import Path

def check_env():
    """Verify .env file and settings."""
    print("\n=== .ENV Configuration ===")
    try:
        from dotenv import load_dotenv
        from config import Config
        
        load_dotenv()
        
        required = [
            "BOT_TOKEN",
            "PHP_API_BASE_URL",
            "PHP_API_SECRET",
            "CALLBACK_SECRET",
            "REDIS_HOST",
            "REDIS_PORT",
        ]
        
        missing = []
        for key in required:
            val = getattr(Config, key, None)
            if not val:
                missing.append(key)
                print(f"  ❌ {key}: MISSING")
            else:
                # Show only first/last part of secrets
                if "SECRET" in key or "TOKEN" in key:
                    if len(str(val)) > 20:
                        display = str(val)[:10] + "..." + str(val)[-10:]
                    else:
                        display = "***"
                else:
                    display = str(val)
                print(f"  ✅ {key}: {display}")
        
        debug_mode = os.getenv("DEBUG", "0")
        print(f"  ✅ DEBUG: {debug_mode}")
        
        if missing:
            print(f"\n⚠️  Missing {len(missing)} required config(s): {', '.join(missing)}")
            return False
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def check_logger():
    """Verify logger setup."""
    print("\n=== Logger Configuration ===")
    try:
        import logging
        from config import Config
        from utils.logger import get_logger
        
        logger = get_logger("test")
        
        # Check logger level
        root_logger = logging.getLogger("reviewrequestbot")
        level = root_logger.level
        level_name = logging.getLevelName(level)
        
        print(f"  ✅ Root logger level: {level_name}")
        print(f"  ✅ DEBUG mode: {Config.DEBUG}")
        print(f"  ✅ Expected level: {'DEBUG' if Config.DEBUG else 'INFO'}")
        
        # Test logging
        logger.info("ℹ️  INFO message (should always appear)")
        logger.debug("🐛 DEBUG message (should appear if DEBUG=1)")
        
        print(f"  ✅ Logger test complete (check output above)")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_redis():
    """Verify Redis connection."""
    print("\n=== Redis Configuration ===")
    try:
        import redis
        from config import Config
        
        r = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        
        r.ping()
        print(f"  ✅ Redis: Connected to {Config.REDIS_HOST}:{Config.REDIS_PORT}")
        
        # Test state storage
        r.set("test_key", "test_value")
        val = r.get("test_key")
        r.delete("test_key")
        
        if val == "test_value":
            print(f"  ✅ Redis: Read/write test passed")
            return True
        else:
            print(f"  ❌ Redis: Read/write failed")
            return False
            
    except Exception as e:
        print(f"  ❌ Redis: {e}")
        return False


def check_bot_token():
    """Verify bot token is valid format."""
    print("\n=== Bot Token Validation ===")
    try:
        from config import Config
        
        token = Config.BOT_TOKEN
        if not token:
            print(f"  ❌ BOT_TOKEN is empty")
            return False
        
        # Telegram bot tokens are like: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
        parts = token.split(":")
        if len(parts) != 2:
            print(f"  ❌ Invalid token format (should have colon)")
            return False
        
        num_part, secret_part = parts
        if not num_part.isdigit() or len(secret_part) < 20:
            print(f"  ⚠️  Token format looks suspicious")
            return False
        
        print(f"  ✅ Bot token format: Valid")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def check_handlers():
    """Verify handlers can be imported."""
    print("\n=== Handlers Registration ===")
    try:
        from telebot.async_telebot import AsyncTeleBot
        from handlers import register_handlers
        
        # Quick check that handlers module has the right functions
        from handlers.start_handler import register_start_handler
        from handlers.photo_handler import register_photo_handler
        from handlers.text_handler import register_text_handler
        
        print(f"  ✅ start_handler: Importable")
        print(f"  ✅ photo_handler: Importable")
        print(f"  ✅ text_handler: Importable")
        
        return True
    except Exception as e:
        print(f"  ❌ Error importing handlers: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_states():
    """Verify state definitions."""
    print("\n=== User States ===")
    try:
        from utils.states import UserStates
        
        states = [
            "start", "awaiting_lang", "awaiting_phone", "awaiting_photo",
            "awaiting_price", "awaiting_description", "submitting"
        ]
        
        for state_name in states:
            if hasattr(UserStates, state_name):
                print(f"  ✅ {state_name}")
            else:
                print(f"  ❌ {state_name}: MISSING")
                return False
        
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("ReviewRequestBot — Configuration Debug")
    print("=" * 60)
    
    checks = [
        ("Environment", check_env),
        ("Logger", check_logger),
        ("Redis", check_redis),
        ("Bot Token", check_bot_token),
        ("Handlers", check_handlers),
        ("States", check_states),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name}: Unhandled exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_pass = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_pass = False
    
    print("\n" + "=" * 60)
    if all_pass:
        print("✅ All checks passed! Bot should start correctly.")
        print("\nNext steps:")
        print("  1. Run: python bot.py")
        print("  2. Open Telegram and send /start to your bot")
        print("  3. Check logs for any errors")
    else:
        print("❌ Some checks failed. Fix the issues above before starting bot.")
    print("=" * 60 + "\n")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())