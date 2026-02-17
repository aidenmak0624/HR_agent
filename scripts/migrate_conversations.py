"""Migration script for converting old conversation data to new models.

This script handles migration from old conversation storage format to the new
Conversation and ConversationMessage models introduced in Iteration 3.

It checks for legacy conversation data and migrates it to the new structure.
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class ConversationMigrator:
    """Handle migration of conversation data to new models."""

    def __init__(self):
        """Initialize migrator."""
        self.stats = {
            'conversations_found': 0,
            'conversations_migrated': 0,
            'messages_migrated': 0,
            'errors': 0,
        }
        self.migration_log = []

    def check_legacy_conversations(self) -> List[Dict[str, Any]]:
        """Check for old conversation data in legacy locations.

        Returns:
            List of legacy conversation dictionaries found
        """
        legacy_conversations = []

        # Check for legacy conversation files
        legacy_dir = os.path.join(
            os.path.dirname(__file__),
            '..',
            'data',
            'legacy_conversations'
        )

        if os.path.exists(legacy_dir):
            for filename in os.listdir(legacy_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(legacy_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                            legacy_conversations.append(data)
                            self.log(f"Found legacy conversation: {filename}")
                    except Exception as e:
                        self.error(f"Error reading {filename}: {str(e)}")

        self.stats['conversations_found'] = len(legacy_conversations)
        return legacy_conversations

    def migrate_conversation(self, legacy_conv: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate a single legacy conversation to new format.

        Args:
            legacy_conv: Legacy conversation dictionary

        Returns:
            Migrated conversation dictionary
        """
        try:
            # Extract basic conversation data
            conversation_id = legacy_conv.get('id', f"conv-{datetime.utcnow().timestamp()}")
            user_id = legacy_conv.get('user_id')
            created_at = legacy_conv.get('created_at', datetime.utcnow().isoformat())
            updated_at = legacy_conv.get('updated_at', datetime.utcnow().isoformat())

            # Validate required fields
            if not user_id:
                self.error(f"Conversation {conversation_id}: missing user_id")
                return None

            # Build new conversation structure
            new_conversation = {
                'conversation_id': conversation_id,
                'user_id': user_id,
                'title': legacy_conv.get('title', 'Migrated Conversation'),
                'status': legacy_conv.get('status', 'active'),
                'created_at': created_at,
                'updated_at': updated_at,
                'metadata': legacy_conv.get('metadata', {}),
                'messages': []
            }

            # Migrate messages
            legacy_messages = legacy_conv.get('messages', [])
            for msg in legacy_messages:
                migrated_msg = self.migrate_message(msg, conversation_id)
                if migrated_msg:
                    new_conversation['messages'].append(migrated_msg)
                    self.stats['messages_migrated'] += 1

            self.stats['conversations_migrated'] += 1
            self.log(f"Migrated conversation: {conversation_id} with {len(new_conversation['messages'])} messages")
            return new_conversation

        except Exception as e:
            self.error(f"Error migrating conversation: {str(e)}")
            return None

    def migrate_message(self, legacy_msg: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
        """Migrate a single message to new format.

        Args:
            legacy_msg: Legacy message dictionary
            conversation_id: ID of parent conversation

        Returns:
            Migrated message dictionary
        """
        try:
            # Extract message data
            message_id = legacy_msg.get('id', f"msg-{datetime.utcnow().timestamp()}")
            sender = legacy_msg.get('sender', 'user')
            content = legacy_msg.get('content', '')
            timestamp = legacy_msg.get('timestamp', datetime.utcnow().isoformat())

            # Determine role from sender
            role = self.map_sender_to_role(sender)

            # Build new message structure
            new_message = {
                'message_id': message_id,
                'conversation_id': conversation_id,
                'role': role,
                'content': content,
                'timestamp': timestamp,
                'metadata': legacy_msg.get('metadata', {}),
            }

            # Preserve optional fields
            if 'intent' in legacy_msg:
                new_message['intent'] = legacy_msg['intent']
            if 'confidence' in legacy_msg:
                new_message['confidence'] = legacy_msg['confidence']
            if 'agent_name' in legacy_msg:
                new_message['agent_name'] = legacy_msg['agent_name']

            return new_message

        except Exception as e:
            self.error(f"Error migrating message: {str(e)}")
            return None

    def map_sender_to_role(self, sender: str) -> str:
        """Map legacy sender type to new role.

        Args:
            sender: Legacy sender type

        Returns:
            New role value
        """
        sender_lower = str(sender).lower()

        role_mapping = {
            'user': 'user',
            'employee': 'user',
            'human': 'user',
            'agent': 'assistant',
            'bot': 'assistant',
            'router': 'assistant',
            'system': 'system',
        }

        return role_mapping.get(sender_lower, 'user')

    def log(self, message: str):
        """Log a migration message.

        Args:
            message: Message to log
        """
        timestamp = datetime.utcnow().isoformat()
        log_entry = f"[{timestamp}] INFO: {message}"
        self.migration_log.append(log_entry)
        print(log_entry)

    def error(self, message: str):
        """Log an error message.

        Args:
            message: Error message to log
        """
        self.stats['errors'] += 1
        timestamp = datetime.utcnow().isoformat()
        log_entry = f"[{timestamp}] ERROR: {message}"
        self.migration_log.append(log_entry)
        print(log_entry)

    def save_migration_report(self):
        """Save migration report to file."""
        report_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'logs',
            f"migration_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        # Ensure logs directory exists
        os.makedirs(os.path.dirname(report_file), exist_ok=True)

        with open(report_file, 'w') as f:
            f.write("CONVERSATION MIGRATION REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Migration Date: {datetime.utcnow().isoformat()}\n")
            f.write("=" * 60 + "\n\n")

            f.write("STATISTICS:\n")
            f.write(f"  Conversations Found:   {self.stats['conversations_found']}\n")
            f.write(f"  Conversations Migrated: {self.stats['conversations_migrated']}\n")
            f.write(f"  Messages Migrated:     {self.stats['messages_migrated']}\n")
            f.write(f"  Errors Encountered:    {self.stats['errors']}\n\n")

            f.write("MIGRATION LOG:\n")
            f.write("=" * 60 + "\n")
            for log_entry in self.migration_log:
                f.write(log_entry + "\n")

        print(f"\nMigration report saved to: {report_file}")

    def print_summary(self):
        """Print migration summary."""
        print("\n" + "=" * 60)
        print("CONVERSATION MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Conversations Found:    {self.stats['conversations_found']}")
        print(f"Conversations Migrated: {self.stats['conversations_migrated']}")
        print(f"Messages Migrated:      {self.stats['messages_migrated']}")
        print(f"Errors:                 {self.stats['errors']}")
        print("=" * 60 + "\n")

    def run(self):
        """Run the migration process."""
        print("\n" + "=" * 60)
        print("CONVERSATION DATA MIGRATION")
        print("=" * 60 + "\n")

        # Check for legacy conversations
        legacy_conversations = self.check_legacy_conversations()

        if not legacy_conversations:
            self.log("No legacy conversations found - nothing to migrate")
            self.print_summary()
            return []

        # Migrate conversations
        migrated_conversations = []
        for legacy_conv in legacy_conversations:
            migrated = self.migrate_conversation(legacy_conv)
            if migrated:
                migrated_conversations.append(migrated)

        # Save migration report
        self.save_migration_report()

        # Print summary
        self.print_summary()

        return migrated_conversations


def main():
    """Main entry point."""
    migrator = ConversationMigrator()
    migrated_conversations = migrator.run()

    # Save migrated conversations to JSON for backup
    if migrated_conversations:
        backup_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'data',
            'migrated_conversations.json'
        )

        os.makedirs(os.path.dirname(backup_file), exist_ok=True)

        with open(backup_file, 'w') as f:
            json.dump(migrated_conversations, f, indent=2)

        print(f"Migrated conversations backup saved to: {backup_file}")


if __name__ == '__main__':
    main()
