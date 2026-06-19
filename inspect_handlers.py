#!/usr/bin/env python3
"""
Handler & State Inspection Script
Helps debug why bot isn't responding to /start
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def main():
    print("\n" + "="*70)
    print("BOT HANDLER & STATE INSPECTION")
    print("="*70)
    
    # ========================================================================
    # 1. Check if handlers are registered
    # ========================================================================
    print("\n[1] Checking Handler Registration")
    print("-" * 70)
    
    try:
        from telebot.async_telebot import AsyncTeleBot
        from config import Config
        from telebot.storage import StateRedisStorage
        
        storage = StateRedisStorage(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
        )
        
        bot = AsyncTeleBot(Config.BOT_TOKEN, state_storage=storage)
        
        # Import handlers (which registers them)
        from handlers import register_handlers
        register_handlers(bot)
        
        print(f"✅ Bot object created: {bot}")
        print(f"✅ Handlers imported and registered")
        
    except Exception as e:
        print(f"❌ Error creating bot: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ========================================================================
    # 2. Inspect message handlers
    # ========================================================================
    print("\n[2] Message Handlers Registered")
    print("-" * 70)
    
    try:
        # pyTelegramBotAPI stores message handlers in bot.message_handlers
        if hasattr(bot, "message_handlers"):
            handlers = bot.message_handlers
            print(f"Total message handlers: {len(handlers)}")
            
            for i, handler in enumerate(handlers, 1):
                filters = handler.get("filters", {})
                
                # Extract filter info
                has_commands = "commands" in filters
                has_state = "state" in filters
                has_func = "func" in filters
                has_content_types = "content_types" in filters
                
                commands = filters.get("commands", [])
                state = filters.get("state", None)
                content_types = filters.get("content_types", [])
                
                print(f"\n  Handler #{i}:")
                if commands:
                    print(f"    Commands: {commands}")
                if has_state:
                    print(f"    State: {state}")
                if content_types:
                    print(f"    Content types: {content_types}")
                if has_func:
                    print(f"    Has custom function: Yes")
                
                # Show callback function name
                if "callback" in handler:
                    callback = handler["callback"]
                    print(f"    Callback: {callback.__name__}")
        else:
            print("⚠️  No message_handlers attribute found")
        
    except Exception as e:
        print(f"❌ Error inspecting handlers: {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================================================
    # 3. Inspect callback handlers
    # ========================================================================
    print("\n[3] Callback Handlers Registered")
    print("-" * 70)
    
    try:
        if hasattr(bot, "callback_query_handlers"):
            handlers = bot.callback_query_handlers
            print(f"Total callback handlers: {len(handlers)}")
            
            for i, handler in enumerate(handlers, 1):
                filters = handler.get("filters", {})
                
                print(f"\n  Callback Handler #{i}:")
                if "callback" in handler:
                    callback = handler["callback"]
                    print(f"    Callback: {callback.__name__}")
                if "func" in filters:
                    print(f"    Has custom function: Yes")
        else:
            print("⚠️  No callback_query_handlers attribute found")
        
    except Exception as e:
        print(f"❌ Error inspecting callbacks: {e}")
    
    # ========================================================================
    # 4. Check Redis for stuck states
    # ========================================================================
    print("\n[4] Redis State Storage")
    print("-" * 70)
    
    try:
        import redis
        
        r = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True,
        )
        
        r.ping()
        print(f"✅ Redis connected: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
        
        # Get all keys
        keys = r.keys("*")
        print(f"\nTotal keys in Redis: {len(keys)}")
        
        if keys:
            print("\nState keys found:")
            for key in sorted(keys):
                try:
                    val = r.get(key)
                    if val and len(val) < 200:
                        print(f"  {key}: {val}")
                    elif val:
                        print(f"  {key}: {val[:100]}... (truncated)")
                    else:
                        print(f"  {key}: (empty)")
                except Exception as e:
                    print(f"  {key}: (error reading - {e})")
        else:
            print("\n⚠️  No keys in Redis state storage yet (empty is normal if bot just started)")
        
    except Exception as e:
        print(f"❌ Error checking Redis: {e}")
    
    # ========================================================================
    # 5. Simulate /start command
    # ========================================================================
    print("\n[5] Handler Test: Simulate /start Command")
    print("-" * 70)
    
    try:
        from telebot.types import Message, User, Chat
        
        # Create mock message
        user = User(id=999999999, is_bot=False, first_name="TestUser", username="testuser")
        chat = Chat(id=999999999, type="private")
        message = Message(
            message_id=1,
            date=0,
            chat=chat,
            from_user=user,
            text="/start",
        )
        
        print(f"Created mock message: /start from user_id={user.id}")
        
        # Try to find a matching handler
        matching_handlers = []
        
        if hasattr(bot, "message_handlers"):
            for handler in bot.message_handlers:
                filters = handler.get("filters", {})
                
                # Check if this handler matches /start
                commands = filters.get("commands")
                if commands and "start" in commands:
                    state = filters.get("state")
                    print(f"\n✅ Found /start handler:")
                    print(f"   Commands: {commands}")
                    print(f"   State filter: {state}")
                    print(f"   Callback: {handler['callback'].__name__}")
                    matching_handlers.append(handler)
        
        if not matching_handlers:
            print("\n❌ NO HANDLER FOUND FOR /start COMMAND")
            print("   This is why bot is not responding!")
        else:
            print(f"\n✅ Found {len(matching_handlers)} matching handler(s)")
        
    except Exception as e:
        print(f"❌ Error in handler test: {e}")
        import traceback
        traceback.print_exc()
    
    # ========================================================================
    # 6. Show expected state flow
    # ========================================================================
    print("\n[6] Expected State Flow")
    print("-" * 70)
    
    try:
        from utils.states import UserStates
        
        flow = [
            ("start", "User sends /start"),
            ("awaiting_lang", "User selects language"),
            ("awaiting_phone", "User provides phone"),
            ("awaiting_photo", "User uploads photos"),
            ("awaiting_price", "User enters price"),
            ("awaiting_description", "User enters description"),
            ("submitting", "System processes request"),
            ("awaiting_photo", "Back to photo upload"),
        ]
        
        print("State progression (normal flow):")
        for i, (state_name, description) in enumerate(flow, 1):
            if hasattr(UserStates, state_name):
                state = getattr(UserStates, state_name)
                print(f"  {i}. {state_name:25} → {description}")
            else:
                print(f"  {i}. {state_name:25} → {description} ⚠️  NOT DEFINED")
        
    except Exception as e:
        print(f"❌ Error showing state flow: {e}")
    
    # ========================================================================
    # 7. Summary
    # ========================================================================
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)
    
    print("""
If you see "NO HANDLER FOUND FOR /start COMMAND" above:
  → Handlers are not being registered to the bot
  → Check handlers/__init__.py is being called
  → Check register_handlers() is returning properly
  
If you see handlers registered but bot still doesn't respond:
  → Issue might be with state filtering or async wrapping
  → Check bot.py compatibility wrapper is working
  → Try clearing Redis state and restarting
  
If you see state keys in Redis:
  → Bot has processed some users
  → Check those users might be stuck in a state
  → Use clear_redis_state.py to reset them
    """)
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
