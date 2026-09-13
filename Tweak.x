#import <Foundation/Foundation.h>
#import <AVFoundation/AVAudioSession.h>

@interface NCNotificationRequest : NSObject
@property (nonatomic, copy, readonly) NSString *sectionIdentifier;
@end

@interface SBMediaController : NSObject
+ (instancetype)sharedInstance;
- (BOOL)isPlaying;
@end

static BOOL SNSomeAppIsPlayingAudio(void) {
    // The Now Playing app is only one possible source of audio. Keep the
    // original check for media playback, but do not rely on it alone.
    Class mediaControllerClass = NSClassFromString(@"SBMediaController");
    if ([mediaControllerClass respondsToSelector:@selector(sharedInstance)]) {
        SBMediaController *mediaController = [mediaControllerClass sharedInstance];
        if ([mediaController respondsToSelector:@selector(isPlaying)] &&
            [mediaController isPlaying]) {
            return YES;
        }
    }

    // Includes other apps' mixable/Ambient audio, even without Now Playing
    // integration. secondaryAudioShouldBeSilencedHint is narrower and would
    // miss that audio. Read the current state; never activate or reconfigure
    // SpringBoard's audio session, and never cache a playing result.
    return [[AVAudioSession sharedInstance] isOtherAudioPlaying];
}

%hook SBNCSoundController
- (BOOL)canPlaySoundForNotificationRequest:(NCNotificationRequest *)request {
    // Preserve the original Clock exemption, including alarms and timers.
    if ([request.sectionIdentifier isEqualToString:@"com.apple.mobiletimer"]) {
        return %orig;
    }

    if (SNSomeAppIsPlayingAudio()) {
        return NO;
    }

    // Let iOS apply its normal mute switch, Focus/DND and notification rules.
    return %orig;
}
%end
