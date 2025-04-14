from typing import Final
import logging
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
    Application

)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for registration conversation
NAME, EMAIL, GITHUB = range(3)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message and start the registration process."""
    user = update.effective_user
    welcome_text = (
        f"Welcome {user.first_name}!\n\n"
        "This bot manages our month-long internship program. "
        "Please register by providing your details."
    )
    await update.message.reply_text(welcome_text)
    await update.message.reply_text("What's your full name?")
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    """Store the name and ask for the email."""
    context.user_data['name'] = update.message.text
    update.message.reply_text("Great! Now please enter your email address.")
    return EMAIL

def get_email(update: Update, context: CallbackContext) -> int:
    """Store the email and ask for the GitHub username."""
    context.user_data['email'] = update.message.text
    update.message.reply_text("Please provide your preferred GitHub username.")
    return GITHUB

def get_github(update: Update, context: CallbackContext) -> int:
    """Store GitHub username and confirm registration."""
    context.user_data['github'] = update.message.text
    
    update.message.reply_text("You are now registered for the internship! 🎉")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the registration conversation."""
    update.message.reply_text("Registration canceled. Type /start to begin again.")
    return ConversationHandler.END

async def help_command(update:Update,context: ContextTypes.DEFAULT_TYPE):
    """
    Purpose: 
    """
    await update.message.reply_text("help_command")
    
# end def


def handle_response(text:str)->str:
    """
    Purpose: 
    """
    
# end def

def main() -> None:
    # Replace 'YOUR_TOKEN' with your bot's API token
    print("Starting....")
    YOUR_TOKEN: Final = "8119953181:AAHWkL432L9UluSMI2730I6iQlS8na1NDuk"
    
    app = Application.builder().token(YOUR_TOKEN).build()

    # Set up a ConversationHandler for the registration process.
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            GITHUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_github)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Add handlers
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))  # Corrected help command handler

    print("Polling.....")
    app.run_polling(poll_interval=2)

if __name__ == '__main__':
    main()
