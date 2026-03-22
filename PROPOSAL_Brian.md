# ThinkStep: AI-Powered Scaffolding for Kids' Thinking

## Problem

When people use AI, the model outputs answers directly. Most users — especially kids — skip the thinking process and jump to the final answer. This erodes children's ability to think independently and reason through problems on their own.

## Solution

**ThinkStep** is an AI-powered learning tool that transforms AI answers into guided, step-by-step thinking exercises. Instead of giving kids the answer, it breaks the AI's reasoning into incremental steps and asks the child to work through each one. The child only progresses when they demonstrate understanding at each stage.

### Example

> **Question:** 1 + 2 + 5 = ?
>
> **Step 1:** "Let's start with the first part. What is 1 + 2?"
> **Child:** "3" ✅
>
> **Step 2:** "Great! Now what is 3 + 5?"
> **Child:** "8" ✅
>
> **Summary:** "You solved it! 1 + 2 = 3, then 3 + 5 = 8. The answer is 8."

## Key Features

### Feature 1: Step-by-Step Decomposition (Core Engine)

The core of the product. When a question is submitted, the AI breaks its answer into a sequence of guided steps. Each step is presented one at a time, and the child must answer correctly before moving on. After all steps are completed, a full summary of the thinking process is shown, reinforcing the learning.

### Feature 2: Adaptive Hints on Mistakes

When a child answers a step incorrectly, the system does not reveal the answer immediately. Instead, it provides progressive hints — starting with a gentle nudge, then a more specific clue, and finally the explanation. This keeps kids in the "zone of proximal development" and prevents frustration.

- **Hint Level 1:** A gentle nudge in the right direction
- **Hint Level 2:** A more specific clue narrowing down the approach
- **Hint Level 3:** Full explanation with the answer

### Feature 3: Age-Adaptive Scaffolding Density

The level of scaffolding adjusts based on the learner's age group, ensuring the product grows with the child:

| Age Group | Strategy | What the child sees |
|-----------|----------|-------------------|
| 5–7 (Early learners) | **Full scaffolding** — every step is broken down explicitly | "What is 1 + 2?" |
| 8–10 (Elementary) | **Partial scaffolding** — only key steps are guided | "This has two parts. Can you figure them out?" |
| 11–14 (Middle school) | **Hint-only** — nudges when stuck, no step breakdown | "Think about simplifying the problem first." |
| 15–18 (High school) | **Challenge mode** — solve independently, then compare with AI's reasoning | "Here's how AI solved it. How does your approach differ?" |

Additionally, the system dynamically adjusts within an age group: consecutive correct answers reduce scaffolding, while repeated mistakes increase support.

### Feature 4: Gamification & Motivation System

To keep kids engaged and build a habit of independent thinking:

- **Thinking Streaks** — consecutive correct steps earn streak bonuses
- **Thinking Coins** — earned through independent problem-solving, redeemable for avatar customization or new topic unlocks
- **"Aha!" Wall** — a collection of the child's breakthrough moments, building a sense of accomplishment
- **Real-time Reward Signals** — immediate, encouraging feedback at each step (e.g., "Well done!", "You're on fire!", "Nice thinking!") to reinforce positive behavior and keep motivation high
- **Leaderboard & Ranking** — weekly/monthly leaderboards among peers (classmates or age group), ranking by thinking streaks, accuracy, and problems solved. Supports both global and class-level rankings to foster healthy competition while keeping it fun

### Feature 5: Parent & Teacher Dashboard

A monitoring interface for parents and teachers to track learning progress:

- **Session Replay** — review the child's step-by-step thinking process for any question
- **Accuracy Analytics** — track correct/incorrect rates across subjects and step types
- **Weakness Detection** — automatically identify which types of reasoning steps the child struggles with most
- **Weekly Report** — summarized progress reports delivered via email or in-app
- **Learning Summarization** — AI-generated summaries that analyze error patterns across domains (e.g., "Your child frequently struggles with carrying in multi-digit addition" or "Reading comprehension errors tend to occur in inference-type questions"). These summaries distill recurring mistakes into high-level lessons and actionable tips that kids can review before their next session

## Target Audience

- **Primary users:** Children and teens aged 5–18
- **Secondary users:** Parents and teachers who want to foster independent thinking skills

## Team Allocation (5 people)

| Member | Responsibility |
|--------|---------------|
| Person 1 | Core AI engine — step decomposition & adaptive hints (Features 1 & 2) |
| Person 2 | Frontend — student-facing step-by-step interaction UI |
| Person 3 | Age-adaptive scaffolding logic & difficulty engine (Feature 3) |
| Person 4 | Gamification system — streaks, coins, achievements (Feature 4) |
| Person 5 | Parent/Teacher dashboard & analytics (Feature 5) |

## Tech Stack (TBD)

- **Frontend:** React / React Native
- **Backend:** Node.js / Python
- **AI:** Claude API for step decomposition and hint generation
- **Database:** PostgreSQL
- **Analytics:** TBD
