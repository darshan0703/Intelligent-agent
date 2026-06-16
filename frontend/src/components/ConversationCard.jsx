export default function ConversationCard({ message }) {
  return (
    <div className="conversation-card">
      <p>{message.text}</p>
    </div>
  );
}