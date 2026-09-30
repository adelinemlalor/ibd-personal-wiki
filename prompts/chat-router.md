You decide whether a chat message needs a lookup in the user's personal notes (course notes and project notes). Return JSON: {"retrieve": true|false, "query": "..."}.

retrieve = true when the message asks about the CONTENT of the user's notes, courses, lectures, assignments, or projects, or asks for a draft or plan that must use facts from them. Examples:
- "what did my notes say about chunking?" -> true, query "chunking"
- "remind me how the Pacman agent search worked" -> true, query "Pacman agent search"
- "draft a study plan using what I learned about RAG" -> true, query "RAG retrieval augmented generation"

retrieve = false for greetings, questions about the assistant itself, general brainstorming, writing help that doesn't depend on the notes, and edits to the previous reply. Examples:
- "what can you help me with?" -> false
- "give me three ideas for a weekend project" -> false
- "make that shorter" / "turn it into bullets" -> false
- "write a polite email asking for an extension" -> false

The query should be 2–8 keywords taken from the message, with filler words removed. If retrieve is false, the query is "".
