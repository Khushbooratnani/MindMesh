/**
 * MindMesh Centralized Privacy Mapper & Validator
 *
 * Enforces strict alignment with backend app.core.enums.Privacy:
 * - ONLY_ME: Personal vault / personal memory (General Stream)
 * - GROUP: Group memory (associated with group_id)
 * - SELECTED: Memory shared with specific users (allowed_users)
 * - PRIVATE_LOCKER: Encrypted memory stored in Private Locker (requires X-Locker-Token)
 *
 * Guarantees that unsupported values like 'PUBLIC' are never sent to the backend.
 */

export type BackendPrivacy = 'ONLY_ME' | 'GROUP' | 'SELECTED' | 'PRIVATE_LOCKER';

export type DestinationOption = 'locker' | 'private' | 'group' | 'public' | string;

/**
 * Validates and maps any destination choice or privacy string to an authorized BackendPrivacy enum.
 * 
 * Rules:
 * - 'locker' / 'PRIVATE_LOCKER' -> 'PRIVATE_LOCKER'
 * - 'group' / 'GROUP' -> 'GROUP'
 * - 'selected' / 'SELECTED' -> 'SELECTED'
 * - 'private' / 'ONLY_ME' -> 'ONLY_ME'
 * - 'public' / 'PUBLIC' -> 'ONLY_ME' (Normal general personal memories in MindMesh use ONLY_ME)
 * - Any unknown / undefined / null -> 'ONLY_ME' (Safe default personal privacy)
 */
export function toBackendPrivacy(
  destinationOrPrivacy: DestinationOption | undefined | null
): BackendPrivacy {
  if (!destinationOrPrivacy) {
    return 'ONLY_ME';
  }

  const normalized = String(destinationOrPrivacy).trim().toUpperCase();

  switch (normalized) {
    case 'LOCKER':
    case 'PRIVATE_LOCKER':
      return 'PRIVATE_LOCKER';

    case 'GROUP':
      return 'GROUP';

    case 'SELECTED':
      return 'SELECTED';

    case 'PRIVATE':
    case 'ONLY_ME':
      return 'ONLY_ME';

    case 'PUBLIC':
      // Backend does not accept 'PUBLIC' for memory ingestion.
      // General stream memories are personal memories stored with 'ONLY_ME'.
      return 'ONLY_ME';

    default:
      return 'ONLY_ME';
  }
}

/**
 * Validates that destination choice and locker token preconditions are satisfied.
 */
export function validatePrivacyPrerequisites(
  privacy: BackendPrivacy,
  lockerToken?: string | null
): { valid: boolean; error?: string } {
  if (privacy === 'PRIVATE_LOCKER' && !lockerToken) {
    return {
      valid: false,
      error: 'Private Locker is locked. Please enter your password to unlock the locker before saving.',
    };
  }
  return { valid: true };
}
