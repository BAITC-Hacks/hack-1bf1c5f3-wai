import { NextResponse } from "next/server";
export function GET() { return NextResponse.json({ ok: true, mode: process.env.OPENAI_API_KEY ? "live" : "demo" }); }

