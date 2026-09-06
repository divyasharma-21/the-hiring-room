"""Sample resume, JD, and answers for one-click Demo Mode."""

DEMO_CANDIDATE = "Ananya Rao"

DEMO_RESUME = """Ananya Rao
Bengaluru, India | ananya.rao@email.com | +91-98XXXXXX21

SUMMARY
Computer Science undergraduate with hands-on experience building backend APIs, React frontends, and small cloud deployments. Interested in backend engineering roles where ownership and reliability matter.

EDUCATION
B.E. Computer Science — Ramaiah Institute of Technology (2022–2026)
CGPA: 8.4/10

SKILLS
Languages: Python, JavaScript, SQL
Frameworks: FastAPI, React, Node.js
Tools: Git, Docker, PostgreSQL, AWS (EC2, S3)
Concepts: REST APIs, basic system design, unit testing

EXPERIENCE
Software Engineering Intern — NovaTech Labs (May 2025 – Jul 2025)
- Built REST APIs in FastAPI for an internal analytics dashboard used by 40+ employees
- Reduced average API latency from ~900ms to ~320ms by adding caching and query optimization
- Wrote unit tests and helped migrate a service to Docker for consistent local setups
- Collaborated with a 4-person team using Agile sprints and code reviews

PROJECTS
Campus Placement Helper
- Web app that matches student resumes to company JDs using keyword + basic semantic overlap
- Stack: React, FastAPI, SQLite

Smart Attendance (Academic)
- Face-recognition attendance prototype for a lab class (OpenCV + Flask)

ACHIEVEMENTS
- IEEE Computer Society student member
- Runner-up, college hackathon 2025 (education track)
"""

DEMO_JD = """Backend Engineer Intern — GrowthOps

We are looking for a Backend Engineer Intern who can own APIs end-to-end and care about reliability.

Responsibilities:
- Design and implement REST APIs using Python (FastAPI preferred)
- Work with PostgreSQL and Redis; write efficient queries
- Containerize services with Docker and help deploy to AWS
- Participate in code reviews, testing, and on-call style debugging for staging issues
- Collaborate with product and frontend to ship features with clear ownership

Requirements:
- Strong Python fundamentals
- Experience with FastAPI or Django/Flask
- Familiarity with SQL and Docker
- Clear communication and ownership mindset
- Bonus: AWS, system design basics, CI/CD

Nice to have:
- React familiarity
- Prior internship or strong projects showing measurable impact
"""

# Sample answers a candidate might give (for optional auto-fill in demo)
DEMO_ANSWERS = [
    "In my internship at NovaTech I worked on the analytics APIs. The dashboard was slow so I looked at the queries and added caching. Latency went down a lot and the team was happy.",
    "When we moved a service to Docker I had to figure out environment differences. I wrote a simple Dockerfile and shared it so everyone had the same setup. That reduced setup issues for new joiners.",
    "I take ownership by clarifying the goal, breaking work into steps, and checking impact after shipping. In the internship I tracked latency before and after my changes so we knew it worked.",
]
