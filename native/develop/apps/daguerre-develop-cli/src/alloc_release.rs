// Modified for Daguerre: incorporated engine, own identity and historical import.
//! Give memory the system allocator keeps after frees back to the system
//! ([`daguerre_develop_engine::memory::set_release_hook`]). The platform call lives in
//! `daguerre-develop-sysmem`, the workspace's only crate allowed `unsafe`.

/// Install the hook.
pub fn install() {
    daguerre_develop_engine::memory::set_release_hook(release);
}

fn release() {
    let _ = daguerre_develop_sysmem::release_free_memory();
}
