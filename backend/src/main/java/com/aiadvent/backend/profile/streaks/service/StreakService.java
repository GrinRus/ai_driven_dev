package com.aiadvent.backend.profile.streaks.service;

import com.aiadvent.backend.profile.streaks.domain.UserStreak;
import com.aiadvent.backend.profile.streaks.persistence.UserStreakRepository;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Service for managing user streaks.
 * Handles streak calculation logic for tracking consecutive daily activity.
 */
@Service
public class StreakService {

  private static final Logger log = LoggerFactory.getLogger(StreakService.class);
  private static final ZoneOffset UTC = ZoneOffset.UTC;

  private final UserStreakRepository repository;

  public StreakService(UserStreakRepository repository) {
    this.repository = repository;
  }

  /**
   * Updates the streak for a given profile based on activity date.
   *
   * <p>Streak calculation rules:
   * <ul>
   *   <li>First activity: creates new streak with current=1, longest=1</li>
   *   <li>Same-day activity: no increment (already counted today)</li>
   *   <li>Consecutive day activity: increment current, update longest if needed</li>
   *   <li>Skip-day activity (gap > 1 day): reset current to 1</li>
   * </ul>
   *
   * @param profileId the profile ID to update streak for
   * @param activeDate the date of activity (in UTC)
   * @return the updated UserStreak record
   * @throws IllegalArgumentException if profileId is null
   */
  @Transactional
  public UserStreak updateStreak(UUID profileId, LocalDate activeDate) {
    if (profileId == null) {
      throw new IllegalArgumentException("profileId cannot be null");
    }
    if (activeDate == null) {
      activeDate = LocalDate.now(UTC);
    }

    log.debug("Updating streak for profileId={}, activeDate={}", profileId, activeDate);

    // Use SELECT FOR UPDATE to lock the row for thread-safe updates
    UserStreak streak = repository.findAndLockByProfileId(profileId)
        .orElse(null);

    if (streak == null) {
      // First activity - create new streak record
      streak = createNewStreak(profileId, activeDate);
      log.debug("Created new streak for profileId={}, current=1, longest=1", profileId);
    } else {
      // Existing streak - apply business logic
      updateExistingStreak(streak, activeDate);
      log.debug("Updated streak for profileId={}, current={}, longest={}",
          profileId, streak.getCurrentStreak(), streak.getLongestStreak());
    }

    return repository.save(streak);
  }

  /**
   * Gets the current streak for a profile.
   *
   * @param profileId the profile ID
   * @return the UserStreak record, or empty if not found
   */
  @Transactional(readOnly = true)
  public java.util.Optional<UserStreak> getStreak(UUID profileId) {
    return repository.findByProfileId(profileId);
  }

  /**
   * Creates a new streak record for first-time activity.
   *
   * @param profileId the profile ID
   * @param activeDate the activity date
   * @return new UserStreak with current=1, longest=1
   */
  private UserStreak createNewStreak(UUID profileId, LocalDate activeDate) {
    UserStreak streak = new UserStreak();
    streak.setProfileId(profileId);
    streak.setCurrentStreak(1);
    streak.setLongestStreak(1);
    streak.setLastActiveDate(activeDate);
    return streak;
  }

  /**
   * Updates an existing streak based on the activity date.
   *
   * @param streak the existing streak record
   * @param activeDate the activity date
   */
  private void updateExistingStreak(UserStreak streak, LocalDate activeDate) {
    LocalDate lastActiveDate = streak.getLastActiveDate();

    if (lastActiveDate == null) {
      // Edge case: existing record without lastActiveDate - treat as first activity
      streak.setCurrentStreak(1);
      streak.setLongestStreak(1);
      streak.setLastActiveDate(activeDate);
      return;
    }

    if (activeDate.equals(lastActiveDate)) {
      // Same-day activity - no increment
      log.debug("Same-day activity detected, not incrementing streak");
      return;
    }

    long daysSinceLastActivity = java.time.temporal.ChronoUnit.DAYS.between(lastActiveDate, activeDate);

    if (daysSinceLastActivity == 1) {
      // Consecutive day activity - increment streak
      int newStreak = streak.getCurrentStreak() + 1;
      streak.setCurrentStreak(newStreak);
      if (newStreak > streak.getLongestStreak()) {
        streak.setLongestStreak(newStreak);
      }
    } else if (daysSinceLastActivity > 1) {
      // Skip-day activity (gap > 1 day) - reset streak to 1
      streak.setCurrentStreak(1);
      // longest_streak is preserved
    } else {
      // Future date or same-day (negative daysSinceLastActivity shouldn't happen with proper input)
      log.debug("Activity date is before last active date, not updating streak");
      return;
    }

    streak.setLastActiveDate(activeDate);
  }
}
