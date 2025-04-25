prompt_library={
    "AI_DESCRIPTION":"""
        **You are an expert copywriter, specifically skilled at translating website and marketing information into simple, friendly, and natural language.** You excel at explaining concepts clearly and briefly, as if talking to a friend.

        **Your Task:**
        Your goal is to write a short, conversational summary of a software product or company. Base your summary *exclusively* on the provided website information (Title, Meta Description, Homepage Content). Imagine you just found out about this thing and are quickly telling a colleague or friend the key takeaway.

        **Inputs Provided:**

        *   `[WEBSITE_TITLE]`: The text from the website's `<title>` tag.
        *   `[META_DESCRIPTION]`: The text from the website's meta description tag.
        *   `[HOME_PAGE_CONTENT]`: The primary textual content extracted from the website's homepage.

        **Output Requirements:**

        **1. Focus - Extract the Essentials (Only if clearly stated in the inputs):**

        *   **What it is:** Quickly state the main purpose or function of the software/company. (e.g., "It's basically a tool that...")
        *   **Who it's for:** Briefly mention the intended audience or users if the text makes it obvious. (e.g., "...aimed at small business owners.") If it's not clear, don't guess.
        *   **Key Help / Benefit:** Highlight 1-2 main ways it helps its users or the key problems it solves, pulling specifics directly from the provided text. (e.g., "It helps you..." or "The main idea is to solve...")
        *   **Core Idea / Vibe:** Briefly capture the central selling point, focus, or overall impression presented on the homepage. (e.g., "Looks like their big focus is on...")

        **2. Style & Tone - Aim for Natural Human Conversation:**

        *   **Conversational & Approachable:** Use simple, everyday language. Write like you're sharing a quick finding. Use contractions (like "it's," "you'll," "they're") naturally. Avoid overly formal or marketing-heavy jargon *unless* it's a core term clearly explained in the input text.
        *   **Direct Opening:** **Do NOT start the summary with conversational filler phrases like "Okay, so...", "Well...", "Basically...", or similar.** Jump straight into explaining what it is or what it does.
        *   **Clear & Concise:** Get straight to the point *from the very first sentence*. Favor shorter sentences and direct phrasing. Think "the gist."
        *   **Very Brief:** Aim for approximately 50-100 words total (usually 1-2 short paragraphs). Shorter is often better if it still covers the key points found in the text.
        *   **Objective & Factual (to the source):** Stick *strictly* to information explicitly present in the provided Title, Description, and Homepage Content. Your *tone* is friendly, but the *information* must be accurate to the source. Do not add external knowledge, opinions, or interpretations.
        *   **Engaging (Subtly):** If it flows naturally, you might briefly frame the summary around a user problem mentioned in the text or a key benefit. But prioritize clarity, brevity, and adherence to the source text above all.

        **3. Format:**

        *   A single block of text.
        *   No bullet points or numbered lists in the final output.

        **Strict Constraints:**

        *   **Source Material Only:** Base the entire summary *only* on the text provided within `[WEBSITE_TITLE]`, `[META_DESCRIPTION]`, and `[HOME_PAGE_CONTENT]`.
        *   **No External Knowledge:** Do not use any information, assumptions, or context from outside these three inputs.
        *   **No Speculation:** If specific information (like the target audience or a key benefit) isn't clearly mentioned in the provided text, do not invent or guess it. Simply omit it.

        **Input Data:**

        [WEBSITE_TITLE]: {Title}
        [META_DESCRIPTION]: {Meta Description}
        [HOME_PAGE_CONTENT]: ```
        {URL Content}```

        Generate the summary now, remembering to sound like a friendly explanation based only on the provided text:
        """,
    "AI_SUMMARY": """
        Write a description of the AI company that is less than 100 characters.
        Here are some inputs you can use to write your description:
        - Website Title: {Title}
        - Website Name: {Name}
        - Website H1: {H1}
        - Website: {URL}
        - Meta description: {Meta Description}
        Do not use marketing speak or jargon. Keep your description simple describing what it is.
        For example, a bad description would be: "Your 24/7 research agents to capture every interaction in the digital universe".
        A good description would be: "Research agents that capture interactions".
        Another example of a bad description is: "A better way to do GTM." That is marketing speak, not an unbiased description of what the product is.
        Another example of a bad description is: "Helps you sell more". Don't tell me what it helps you do. Tell me what it is.
        Another bad example: "Makes data-driven decisions for retail and e-commerce." Don't tell me what it does. Tell me what it is.

        Do not start your descriptions with "AI company...". Everyone already knows it's an AI company. The goal is to describe what their product is.""",
    "AI_TAGS": """
        Here is the content of the website for an application: {URL_Content}

        Based on this content, tag the content with one of the following tags:

        Market Research
        Real Estate
        Image Generation
        Content Creation
        Construction
        E-Commerce
        Blockchain
        Legal
        Multi-Agent Workflows
        Document Analysis
        Media
        Databases
        Assistant
        Scheduling
        Security
        Education
        Audio
        Observability
        AI Chatbot
        Inventory Management
        Travel
        Inbox Management
        SEO/SEM
        Data Analysis
        Web 3
        Model Serving
        Data Cleaning
        Security Compliance
        Web Scraping
        Coaching
        Lead Generation
        Frontend
        AI Model Sharing
        Browser Agents
        Speech AI
        Financial Infrastructure
        Logistics
        Open-Source LLMs
        AI Infrastructure
        Identity Verification
        Audio AI
        Ads
        Contract Review
        Consulting AI Tools
        Operations Agents
        Financial Services
        Email
        Workflow Automation
        Trade Data Analytics
        Language Learning
        Web Platforms
        Chatbot
        Procurement
        Robotics
        Recruiting
        Medical
        APIs
        Coding Library
        Bookkeeping
        Research
        Compliance
        ERP Automation
        Voice AI
        Avatar
        Prototyping
        Cloud Computing
        Voice Agents
        AI Docs
        Web Marketing
        Analytics
        Sales Agent
        Digital Workers
        Model APIs
        Customer Support
        Data Enrichment
        Copywriting
        Coding Assistant
        Vector Databases
        Insurance
        RPA
        Digital Interaction Analytics
        Social Media Marketing
        Translation
        Supply Chain Analytics
        AI-Powered Search
        Text-to-Speech
        Coding Agent
        Hiring
        Pricing
        Writing Tools
        Agents Platform
        Personal Assistant
        Software Testing
        Tax Automation
        DIY/Build Your Own
        General Purpose
        Note-Taking
        Predictive AI
        Video Editing
        CRM
        Graphic Design
        Productivity
        Prompt Engineering
        Knowledge Base
        Web AI Agents
        Text-to-App
        Workflow
        Digital Interaction Analysis
        Video Marketing
        AI Databases
        Shopping
        Virtual desktops
        Design Tools
        Project Management

        If you cannot determine the tag, respond with only "-" and nothing else.

        Only respond with the tag. Do not include any other text. Do not respond with any tags that are not on the above list.

        Only respond with one tag.
    """,
}
