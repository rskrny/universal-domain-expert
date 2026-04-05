# LPT If you ever forget your WiFi password or you want to get your school WiFi password etc. Just type this command into the command line of a computer already connected to that WiFi: netsh wlan show profile WiFi-name key=clear

Source: https://reddit.com/r/LifeProTips/comments/d5vknk/lpt_if_you_ever_forget_your_wifi_password_or_you/
Subreddit: r/LifeProTips | Score: 103940 | Date: 2019-09-18
Engagement: 1.0 | Practical Value: high

## Extracted Claims

**Claim 1:** Windows computers store WiFi passwords in cleartext that can be retrieved via the netsh wlan show profile command, allowing recovery of forgotten passwords from any connected device.
- Evidence: tutorial (confidence: 0.95)
- Details: The post provides a specific Windows command (netsh wlan show profile WiFi-name key=clear) that retrieves stored WiFi passwords from a computer already connected to a network. This is a documented Windows feature that exposes a security/convenience tradeoff. The high engagement (103K upvotes) suggests the technique works as described.

**Claim 2:** Hotel business center computers connected to employee WiFi can be used to extract passwords for paid or restricted WiFi networks that guests would otherwise need to pay to access.
- Evidence: anecdote (confidence: 0.75)
- Details: The top comment applies the password recovery technique to a specific scenario: accessing hotel WiFi without paying by finding an employee-connected computer. This represents a practical application but relies on the assumption that business center computers have accessible WiFi credentials and that this bypasses guest restrictions.

## Key Data Points
- 103940 (post score)
- 2841 (comment count)
- 15598 (top comment score)

**Novelty:** This is a well-known Windows administrative feature among IT professionals, but appears to be emerging knowledge for general consumers seeking a legitimate solution to password recovery.

## Counterarguments
- The technique requires local administrative access to the computer, which limits applicability for many scenarios
- The hotel WiFi bypass use case raises ethical and legal concerns that may violate terms of service
- Modern alternatives like password managers or account recovery through ISP portals may be more appropriate for legitimate password recovery

---


## Top Comments

**u/ihavethebestmarriage** (15598 pts):
> Corollary LPT: when youre at a hotel that charges for wifi (or for faster wifi), get the password from the business center computer which is probably connected to the employee wifi
