//! Best-effort release of allocator-retained pages after an engine invocation.
//!
//! Tectonic's native engine performs many large, short-lived allocations. On
//! macOS, freed pages may remain resident in malloc-zone caches. The product
//! runs inside Stata, so retaining hundreds of megabytes after repeated calls
//! is undesirable even when those pages are no longer live. This guard asks the
//! system allocator to release all available cached pages after the complete
//! compilation stack has been dropped.

/// Trigger platform memory-pressure relief when dropped.
pub(crate) struct MemoryPressureReliefGuard;

impl MemoryPressureReliefGuard {
    pub(crate) const fn new() -> Self {
        Self
    }
}

impl Drop for MemoryPressureReliefGuard {
    fn drop(&mut self) {
        platform::release_unused_pages();
    }
}

#[cfg(target_os = "macos")]
mod platform {
    use std::{ffi::c_void, ptr};

    unsafe extern "C" {
        fn malloc_zone_pressure_relief(zone: *mut c_void, goal: usize) -> usize;
    }

    pub(super) fn release_unused_pages() {
        // Apple documents zone=NULL as examining all malloc zones and goal=0 as
        // requesting maximal pressure relief. The function is best-effort; the
        // returned byte count is diagnostic only and does not affect success.
        unsafe {
            let _ = malloc_zone_pressure_relief(ptr::null_mut(), 0);
        }
    }
}

#[cfg(not(target_os = "macos"))]
mod platform {
    pub(super) fn release_unused_pages() {}
}

#[cfg(test)]
mod tests {
    use super::MemoryPressureReliefGuard;

    #[test]
    fn pressure_relief_guard_is_safe_to_drop() {
        drop(MemoryPressureReliefGuard::new());
    }
}
