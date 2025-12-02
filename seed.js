const { PrismaClient } = require('./generated/prisma');
const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database with test data...\n');

  // Create a test user
  const user = await prisma.users.create({
    data: {
      first_name: 'John',
      surname: 'Doe',
      email: 'john.doe@example.com',
      phone_number: '+1234567890',
      age: 28,
      password_hash: 'hashed_password_here',
      created_at: new Date()
    }
  });
  console.log(`✅ Created user: ${user.first_name} ${user.surname} (ID: ${user.id})`);

  // Create user tokens
  const tokens = await prisma.user_tokens.create({
    data: {
      user_id: user.id,
      balance: 150,
      updated_at: new Date()
    }
  });
  console.log(`✅ Created token wallet with ${tokens.balance} tokens`);

  // Create user profile
  const profile = await prisma.user_profiles.create({
    data: {
      user_id: user.id,
      display_name: 'John Doe',
      role: 'Producer',
      bio: 'Music producer and beat maker',
      created_at: new Date()
    }
  });
  console.log(`✅ Created user profile for ${profile.display_name}`);

  // Create chat messages
  const msg1 = await prisma.chat_messages.create({
    data: {
      session_id: 'demo-session-001',
      message_type: 'user',
      content: 'Hello! Can you help me find some beats?',
      created_at: new Date()
    }
  });

  const msg2 = await prisma.chat_messages.create({
    data: {
      session_id: 'demo-session-001',
      message_type: 'assistant',
      content: 'Of course! I can help you find the perfect beats. What genre are you interested in?',
      created_at: new Date()
    }
  });
  console.log(`✅ Created ${2} chat messages`);

  // Create audio pack
  const pack = await prisma.audio_packs.create({
    data: {
      user_id: user.id,
      title: 'Summer Vibes Beat Pack',
      description: 'Collection of upbeat summer-themed beats perfect for any project',
      genre: 'Hip-Hop',
      bpm: 120,
      musical_key: 'C Major',
      created_at: new Date()
    }
  });
  console.log(`✅ Created audio pack: ${pack.title}`);

  // Create audio files
  const file1 = await prisma.audio_files.create({
    data: {
      pack_id: pack.id,
      title: 'Summer Beat 01',
      file_url: '/uploads/audio/summer_beat_01.mp3',
      tokens_listen: 1,
      tokens_download: 3,
      duration_seconds: 180,
      created_at: new Date()
    }
  });

  const file2 = await prisma.audio_files.create({
    data: {
      pack_id: pack.id,
      title: 'Summer Beat 02',
      file_url: '/uploads/audio/summer_beat_02.mp3',
      tokens_listen: 1,
      tokens_download: 3,
      duration_seconds: 165,
      created_at: new Date()
    }
  });
  console.log(`✅ Created 2 audio files in pack`);

  // Create user activity
  const activity = await prisma.user_activity.create({
    data: {
      user_id: user.id,
      type: 'UPLOAD',
      entity_id: pack.id,
      entity_type: 'PACK',
      created_at: new Date()
    }
  });
  console.log(`✅ Created user activity log`);

  // Create feedback
  const feedback = await prisma.feedback.create({
    data: {
      user_id: user.id,
      understand_clarity: 5,
      start_ease: 4,
      design_rating: 5,
      answers_helpful: 4,
      response_speed: 5,
      use_again_likelihood: 9,
      recommend_likelihood: 8,
      created_at: new Date()
    }
  });
  console.log(`✅ Created feedback entry`);

  console.log('\n🎉 Database seeded successfully!');
  console.log('📊 Summary:');
  console.log('   - 1 user');
  console.log('   - 1 user profile');
  console.log('   - 1 token wallet');
  console.log('   - 2 chat messages');
  console.log('   - 1 audio pack');
  console.log('   - 2 audio files');
  console.log('   - 1 activity log');
  console.log('   - 1 feedback');
}

main()
  .catch(e => {
    console.error('Error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
