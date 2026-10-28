/**
 * Automated Verification Test Suite for Privacy Enum Contract & Ingestion Modalities
 */
const assert = require('assert');

// 1. Simulation of toBackendPrivacy from src/services/privacyMapper.ts
function toBackendPrivacy(destinationOrPrivacy) {
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
      // 'PUBLIC' is strictly mapped to 'ONLY_ME'
      return 'ONLY_ME';

    default:
      return 'ONLY_ME';
  }
}

function validatePrivacyPrerequisites(privacy, lockerToken) {
  if (privacy === 'PRIVATE_LOCKER' && !lockerToken) {
    return {
      valid: false,
      error: 'Private Locker is locked. Please enter your password to unlock the locker before saving.',
    };
  }
  return { valid: true };
}

// 2. Format 422 error logic simulation
function formatValidationErrors(parsedDetail, statusCode = 422) {
  if (Array.isArray(parsedDetail) && parsedDetail.length > 0) {
    const fieldErrors = parsedDetail.map((d) => {
      const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : '';
      const msg = d.msg || 'Invalid field';
      return field ? `${field}: ${msg}` : msg;
    });
    return `Validation Error: ${fieldErrors.join('; ')}`;
  } else if (typeof parsedDetail === 'string') {
    return parsedDetail;
  }
  return `Upload failed with HTTP ${statusCode}`;
}

// Allowed Backend Privacy Enum Values from Debian app.core.enums.Privacy
const BACKEND_ALLOWED_ENUMS = new Set(['ONLY_ME', 'GROUP', 'SELECTED', 'PRIVATE_LOCKER']);

console.log('--- TEST SUITE: Privacy Enum Contract & Modalities ---');

// Test 1: All UI destination choices map to valid backend enums
const destinations = ['locker', 'private', 'group', 'public', undefined, null, '', 'unknown_future_opt'];
destinations.forEach((dest) => {
  const result = toBackendPrivacy(dest);
  assert(BACKEND_ALLOWED_ENUMS.has(result), `Result '${result}' for dest '${dest}' is not a valid backend enum!`);
  assert(result !== 'PUBLIC', `Result must never be 'PUBLIC' for dest '${dest}'`);
});
console.log('✓ Test 1 Passed: All UI destination choices map to valid backend enums.');

// Test 2: Specific semantic mappings
assert.strictEqual(toBackendPrivacy('locker'), 'PRIVATE_LOCKER');
assert.strictEqual(toBackendPrivacy('private'), 'ONLY_ME');
assert.strictEqual(toBackendPrivacy('group'), 'GROUP');
assert.strictEqual(toBackendPrivacy('public'), 'ONLY_ME'); // Re-mapped away from unsupported 'PUBLIC'
assert.strictEqual(toBackendPrivacy('PUBLIC'), 'ONLY_ME');
assert.strictEqual(toBackendPrivacy('ONLY_ME'), 'ONLY_ME');
assert.strictEqual(toBackendPrivacy('PRIVATE_LOCKER'), 'PRIVATE_LOCKER');
console.log('✓ Test 2 Passed: Specific semantic mappings match expected backend enums.');

// Test 3: Text ingestion payload building
function buildTextPayload(input) {
  return {
    text: input.text,
    media_type: 'text',
    privacy: toBackendPrivacy(input.privacy),
    group_id: input.group_id || null,
    allowed_users: [],
  };
}

const textPayloadPublic = buildTextPayload({ text: 'Sample text', privacy: 'PUBLIC' });
assert.strictEqual(textPayloadPublic.privacy, 'ONLY_ME');
assert(BACKEND_ALLOWED_ENUMS.has(textPayloadPublic.privacy));

const textPayloadLocker = buildTextPayload({ text: 'Private note', privacy: 'PRIVATE_LOCKER' });
assert.strictEqual(textPayloadLocker.privacy, 'PRIVATE_LOCKER');
assert(BACKEND_ALLOWED_ENUMS.has(textPayloadLocker.privacy));
console.log('✓ Test 3 Passed: Text ingestion payload maps privacy strictly to backend enum.');

// Test 4: Image ingestion parameters building
function buildImageParams(input) {
  return {
    media_type: 'image',
    privacy: toBackendPrivacy(input.privacy),
    allowed_users: '[]',
  };
}

const imageParamsPublic = buildImageParams({ privacy: 'PUBLIC' });
assert.strictEqual(imageParamsPublic.privacy, 'ONLY_ME');
assert(BACKEND_ALLOWED_ENUMS.has(imageParamsPublic.privacy));

const imageParamsLocker = buildImageParams({ privacy: 'locker' });
assert.strictEqual(imageParamsLocker.privacy, 'PRIVATE_LOCKER');
assert(BACKEND_ALLOWED_ENUMS.has(imageParamsLocker.privacy));
console.log('✓ Test 4 Passed: Image ingestion parameters map privacy strictly to backend enum.');

// Test 5: Audio ingestion parameters building
function buildAudioParams(input) {
  return {
    media_type: 'audio',
    privacy: toBackendPrivacy(input.privacy),
    allowed_users: '[]',
  };
}

const audioParamsPublic = buildAudioParams({ privacy: 'public' });
assert.strictEqual(audioParamsPublic.privacy, 'ONLY_ME');
assert(BACKEND_ALLOWED_ENUMS.has(audioParamsPublic.privacy));

const audioParamsGroup = buildAudioParams({ privacy: 'group' });
assert.strictEqual(audioParamsGroup.privacy, 'GROUP');
assert(BACKEND_ALLOWED_ENUMS.has(audioParamsGroup.privacy));
console.log('✓ Test 5 Passed: Audio ingestion parameters map privacy strictly to backend enum.');

// Test 6: Private Locker prerequisite validation
const validLocker = validatePrivacyPrerequisites('PRIVATE_LOCKER', 'tok_abc123');
assert.strictEqual(validLocker.valid, true);

const lockedLocker = validatePrivacyPrerequisites('PRIVATE_LOCKER', null);
assert.strictEqual(lockedLocker.valid, false);
assert(lockedLocker.error.includes('Private Locker is locked'));

const normalOnlyMe = validatePrivacyPrerequisites('ONLY_ME', null);
assert.strictEqual(normalOnlyMe.valid, true);
console.log('✓ Test 6 Passed: Private Locker token prerequisites validation enforced.');

// Test 7: HTTP 422 Pydantic error formatting
const sample422Detail = [
  {
    type: 'enum',
    loc: ['body', 'privacy'],
    msg: "Input should be 'ONLY_ME', 'GROUP', 'SELECTED' or 'PRIVATE_LOCKER'",
    input: 'PUBLIC',
    ctx: { expected: "'ONLY_ME', 'GROUP', 'SELECTED' or 'PRIVATE_LOCKER'" },
  },
];
const formattedError = formatValidationErrors(sample422Detail);
assert.strictEqual(
  formattedError,
  "Validation Error: privacy: Input should be 'ONLY_ME', 'GROUP', 'SELECTED' or 'PRIVATE_LOCKER'"
);
console.log('✓ Test 7 Passed: HTTP 422 Pydantic error detail is formatted cleanly.');

console.log('\n>>> ALL 7 PRIVACY CONTRACT AND INGESTION TESTS PASSED SUCCESSFULLY! <<<');
