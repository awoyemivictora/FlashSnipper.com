import axios from "axios";
import dotenv from 'dotenv';

dotenv.config();


export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}


export async function sendTelegramMessage(message) {
    try {
        const response = await axios.post(`https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
            chat_id: process.env.TELEGRAM_CHAT_ID,
            text: message,
            parse_mode: 'MarkdownV2',
        });
        // console.log("📩 Telegram message sent:", response.data);
    } catch (error) {
        console.error("❌ Error sending Telegram message:", error);
    }
}