import { Client } from "pg";
import dotenv from 'dotenv';


dotenv.config();


const client = new Client({
    connectionString: process.env.DATABASE_URL,
});


await client.connect();
console.log("✅ Connected to PostgreSQL");


export default client;