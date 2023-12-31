def get_model(args, **kwargs):       
    if args.model.framework == 'UNISURF':
        from .unisurf import get_model
    elif args.model.framework == 'NeuS':
        from .neus import get_model
    elif args.model.framework == 'VolSDF':
        from .volsdf import get_model
    elif args.model.framework == 'VolSDFHOI':
        from .volsdf_hoi import get_model
    else:
        raise NotImplementedError
    return get_model(args, **kwargs)

